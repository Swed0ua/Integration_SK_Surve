import json
import os
import time

from dotenv import load_dotenv

from core.logger import LOG_LEVEL_ERROR, LOG_LEVEL_WARNING
from services.DBService import add_receipt, receipt_exists, update_add_payment_correlationId, update_close_order_correlationId, update_receipt_step
from services.LoggerService import LoggerService
from services.SmartKasaService import SmartKasaService
from services.SyrveService import SyrveService

load_dotenv()

class SyncBridge:
    def __init__(self, smartkasa_conf: dict, syrve_conf: dict):
        self.smartkasa = SmartKasaService(**smartkasa_conf)
        self.syrve = SyrveService(api_login=syrve_conf["api_login"])

    def sync_last_receipts(self):
        try:
            LoggerService.log(main_msg="[SmartKasa] Authorization...")

            self.smartkasa.authenticate()
            LoggerService.log(main_msg="[SmartKasa] ✅ Authorization successful.")

            LoggerService.log(main_msg="[SmartKasa] Getting receipts...")
            receipts = self.smartkasa.get_invoices_all_pages()
            
            with open("receipts.json", "w", encoding="utf-8") as f:
                json.dump(receipts, f, indent=4, ensure_ascii=False)
            
            # TODO: Mock data
            # date_from = "2025-06-01"
            date_from = "2025-10-10"

            receipts = self.smartkasa.filter_receipts_by_date(receipts, date_from=date_from, date_to=None)

            LoggerService.log(main_msg=f"[SmartKasa] 🔎 Found {len(receipts)} receipts from {date_from}.")
        
            if not receipts:
                print()
                LoggerService.log(main_msg=f"[SmartKasa] ⚠️ No receipts found.", level=LOG_LEVEL_WARNING)
                return

            LoggerService.log(main_msg=f"[Syrve] Authorization...")

            self.syrve.authenticate()
            LoggerService.log(main_msg=f"[Syrve] ✅ Authorization successful.")
            
            org_id = self.syrve.get_organization_id()
            term_id = self.syrve.get_terminal_group_id(org_id)
            nomenclature = self.syrve.get_nomenclature(org_id)

            LoggerService.log(main_msg=f"[Syrve] Receipts count {len(receipts)}")

            for idx, receipt in enumerate(receipts, 1):
                print("="*60)
                sk_receipt_id = receipt.get("id")

                if receipt_exists(sk_receipt_id):
                    LoggerService.log(main_msg=f"[DB]  Processing receipt #{idx}, Receipt already exists in DB: {sk_receipt_id}")
                    continue

                LoggerService.log(main_msg=f"[SmartKasa] ▶️ Processing receipt #{idx} | SK_ID: {sk_receipt_id} | Date: {receipt.get('created_at')}", msg_log_db=f"Receipt: {receipt}")

                items = []
                for item in receipt.get("items", []):
                    product_id = item.get("product_id")
                    quantity = item.get("quantity", 1)
                    price = item.get("price", 0.0)

                    smartkasa_product = self.smartkasa.get_product_by_id(product_id)
                    if not smartkasa_product:
                        error_msg = f"SmartKasa product not found: {product_id}. SK_ID: {sk_receipt_id}, Item: {item}"
                        LoggerService.log(main_msg=f"[SmartKasa][!] ❌ {error_msg}", level=LOG_LEVEL_ERROR)
                        raise ValueError(error_msg)

                    product_code = smartkasa_product.get("alter_number")
                    LoggerService.log(main_msg=f"[SmartKasa] ➡️ Product: {smartkasa_product.get('alter_title')} (Code: {product_code}, Quantity: {quantity}, Price: {price})")

                    syrve_product = self.syrve.find_product_by_code(nomenclature, product_code)

                    if not syrve_product:
                        error_msg = f"Product with code {product_code} not found in Syrve. SK_ID: {sk_receipt_id}, Product: {smartkasa_product.get('alter_title')}"
                        LoggerService.log(main_msg=f"[Syrve][!] ❌ {error_msg}", level=LOG_LEVEL_ERROR)
                        raise ValueError(error_msg)

                    items.append({
                        "productId": syrve_product["id"],
                        "type": "Product",
                        "amount": quantity,
                        "price": price
                    })

                if not items:
                    LoggerService.log(main_msg=f"[SmartKasa][!] ⚠️ No products matched for the order. SK_ID[{sk_receipt_id}]", msg_log_db=f"Receipts: {receipt.get("items", [])}", level=LOG_LEVEL_WARNING)
                    continue

                discount_amount = receipt.get('discount_amount')
                discountsInfo = None
                if discount_amount and float(discount_amount) > 0:

                    discount_type_id = os.getenv("SURVE_DISCOUT_TYPE_ID")
                    discount_type = os.getenv("SURVE_DISCOUT_TYPE")

                    discountsInfo = {
                        "discounts": [
                            {
                                "discountTypeId": discount_type_id,
                                "sum": float(discount_amount),
                                "type": discount_type
                            }
                        ]
                    }

                payment_tx = receipt.get('payment_transactions', [{}])[0]
                transaction_type_id = payment_tx.get('transaction_type_id')
                amount = float(payment_tx.get('amount', 0))
                
                if transaction_type_id == 0:
                    cash_pay_id = os.getenv("SURVE_TRANSACTION_TYPE_ID_CASH")
                    payment_type_id = cash_pay_id
                    payment_type_kind = "Card"
                else:
                    card_pay_id = os.getenv("SURVE_TRANSACTION_TYPE_ID_CARD")
                    payment_type_id = card_pay_id
                    payment_type_kind = "Card"
                
                payments = [{
                    "paymentTypeId": payment_type_id,
                    "paymentTypeKind": payment_type_kind,
                    "sum": amount
                }]
                
                LoggerService.log(main_msg=f"[SmartKasa] Discount: {discountsInfo}, SK_ID[{sk_receipt_id}]")

                LoggerService.log(main_msg=f"[Syrve] 📝 Creating order..., SK_ID[{sk_receipt_id}]")

                result = self.syrve.create_order(org_id, term_id, items, discountsInfo=discountsInfo)
                order_info = result.get("orderInfo", {})
                receipt_id = order_info.get("id")
                add_receipt(
                    id=receipt_id,
                    created_at=order_info.get("timestamp"), 
                    step="create_order",
                    status=order_info.get("creationStatus"),
                    data=str(order_info),
                    sk_created_at=receipt.get("created_at"),
                    sk_status=receipt.get("state"),
                    sk_id=receipt.get("id"),
                    surve_id=order_info.get("id"),
                    payment_type=payment_type_kind,
                    amount=str(amount),
                    discount=str(discount_amount),
                    create_order_correlationId=result.get("correlationId"),
                    add_payment_correlationId=add_payment_result.get("correlationId") if 'add_payment_result' in locals() else None,
                    close_order_correlationId=close_order_result.get("correlationId") if 'close_order_result' in locals() else None
                )
                LoggerService.log(main_msg=f"[Syrve] ✅ Order created, SK_ID[{sk_receipt_id}]", msg_log_db=f"Order: {result}", receipt_id=receipt_id)

                # Add payment
                LoggerService.log(main_msg=f"[SmartKasa] 💳 Payment type, SK_ID[{sk_receipt_id}]: {payment_type_kind} (ID: {payment_type_id}), Amount: {amount}", receipt_id=receipt_id)
                time.sleep(5)

                add_payment_result = self.syrve.add_payment(org_id, result["orderInfo"]["id"], payments)
                LoggerService.log(main_msg=f"[Syrve] ✅ Payment added to order, SK_ID[{sk_receipt_id}], {result['orderInfo']['id']} ", msg_log_db=add_payment_result, receipt_id=receipt_id)
                update_receipt_step(receipt_id, "add_payment")
                update_add_payment_correlationId(receipt_id, add_payment_result.get("correlationId"))

                close_order_result = self.syrve.close_order(org_id, result["orderInfo"]["id"])
                LoggerService.log(main_msg=f"[Syrve] ✅ Order {result['orderInfo']['id']} closed., SK_ID[{sk_receipt_id}]", msg_log_db=close_order_result, receipt_id=receipt_id)
                print("="*60)
                update_receipt_step(receipt_id, "close_order")
                update_close_order_correlationId(receipt_id, close_order_result.get("correlationId"))

        except Exception as e:
            LoggerService.log(main_msg=f"[X] ❌ Error in SyncBridge: {e}", level=LOG_LEVEL_ERROR)

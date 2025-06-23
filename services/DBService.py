from peewee import Model, SqliteDatabase, CharField, TextField, DateTimeField, AutoField
from datetime import datetime

DB_PATH = "syncbridge.db"
db = SqliteDatabase(DB_PATH)

class BaseModel(Model):
    class Meta:
        database = db

class Receipt(BaseModel):
    id = CharField(primary_key=True)
    created_at = CharField()
    step = CharField()
    status = CharField()
    data = TextField()
    sk_created_at = CharField()
    sk_status = CharField()
    sk_id = CharField()
    surve_id = CharField()
    payment_type = CharField(null=True)
    amount = CharField(null=True)
    discount = CharField(null=True)
    create_order_correlationId = CharField(null=True)
    add_payment_correlationId = CharField(null=True)
    close_order_correlationId = CharField(null=True)

class Log(BaseModel):
    id = AutoField()
    timestamp = DateTimeField(default=datetime.now)
    level = CharField()
    message = TextField()
    receipt_id = CharField(null=True)

def init_db():
    db.connect()
    db.create_tables([Receipt, Log], safe=True)
    db.close()

def add_receipt(**kwargs):
    Receipt.replace(**kwargs).execute()

def add_log(level, message, receipt_id=None):
    Log.create(
        level=level,
        message=message,
        receipt_id=receipt_id
    )

def update_receipt_step(receipt_id, new_step):
    query = Receipt.update(step=new_step).where(Receipt.id == receipt_id)
    return query.execute()
def update_add_payment_correlationId(receipt_id, correlation_id):
    query = Receipt.update(add_payment_correlationId=correlation_id).where(Receipt.id == receipt_id)
    return query.execute()
def update_close_order_correlationId(receipt_id, correlation_id):
    query = Receipt.update(close_order_correlationId=correlation_id).where(Receipt.id == receipt_id)
    return query.execute()

def receipt_exists(sk_receipt_id):
    return Receipt.select().where(Receipt.sk_id == sk_receipt_id).exists()
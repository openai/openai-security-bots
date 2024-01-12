from peewee import *
from playhouse.db_url import *
import os

db_url = os.getenv("DATABASE_URL") or "postgres://postgres:postgres@localhost:5432/postgres"
db = connect(db_url)


class BaseModel(Model):
    class Meta:
        database = db


class Assessment(BaseModel):
    project_name = CharField(unique=True)
    project_description = TextField()
    links_to_resources = TextField(null=True)
    point_of_contact = CharField()
    estimated_go_live_date = CharField(null=True)
    outcome = CharField(null=True)
    decision = CharField(null=True)
    justification = TextField(null=True)


class Question(Model):
    question = TextField()
    answer = TextField(null=True)
    assessment = ForeignKeyField(Assessment, backref="questions")

    class Meta:
        database = db
        indexes = ((("question", "assessment"), True),)


class Resource(BaseModel):
    url = TextField()
    content_hash = CharField()
    assessment = ForeignKeyField(Assessment, backref="resources")


db.connect()
db.create_tables([Assessment, Question, Resource])

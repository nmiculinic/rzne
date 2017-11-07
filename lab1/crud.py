import hashlib
import logging
import os

import falcon
import hug
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from toolz import itertoolz

Base = declarative_base()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
"""
  Helper Methods
"""

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class User(Base):
    __tablename__ = 'users'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String, unique=True)
    salt = sa.Column(sa.BLOB)
    hash = sa.Column(sa.BLOB)
    notes = relationship(
        "Notes", backref="owner", cascade="all, delete, delete-orphan")

    def __repr__(self):
        return f"<User(name={self.name}, salt={self.salt}, hash={self.hash})>"


class Notes(Base):
    __tablename__ = 'notes'
    id = sa.Column(sa.Integer, primary_key=True)
    text = sa.Column(sa.TEXT)
    owner_id = sa.Column(sa.Integer, sa.ForeignKey('users.id'))


engine = create_engine('sqlite:////tmp/foo.db')
Session = sessionmaker(bind=engine)


def hash_password(password, salt):
    """
    Securely hash a password using a provided salt
    :param password:
    :param salt:
    :return: Hex encoded SHA512 hash of provided password
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA512(),
        length=32,
        salt=salt,
        iterations=1 if "CI" in os.environ else 100000,
        backend=default_backend())
    return hashlib.sha512(kdf.derive(password.encode("UTF-8"))).digest()


@hug.cli()
def authenticate_user(username, password):
    """
    Authenticate a username and password against our database
    :param username:
    :param password:
    :return: authenticated username
    """
    session = Session()
    user: User = session.query(User).filter(User.name == username).first()

    if not user:
        logger.warning("User %s not found", username)
        return False

    if user.hash == hash_password(password, user.salt):
        return user

    return False


basic_authentication = hug.authentication.basic(authenticate_user)

###
# User stuff
###


@hug.post('/user/{username}', requires=basic_authentication)
@hug.cli()
@hug.local()
def add_user(username, password, response=None):
    """
    CLI Parameter to add a user to the database
    :param username:
    :param password:
    :return: JSON status output
    """

    session = Session()
    if session.query(User).filter(User.name == username).first() is not None:
        response.status = falcon.HTTP_400
        return "Username exists"

    salt = hashlib.sha512(str(os.urandom(64)).encode('utf-8')).digest()
    password_hash = hash_password(password, salt)
    user = User(
        name=username,
        salt=salt,
        hash=password_hash,
    )

    session.add(user)
    session.commit()
    if response is not None:
        response.status = falcon.HTTP_201
        response._headers['Location'] = f"/user/{username}"
    return {'result': 'success', 'eid': user.id}


@hug.get('/test_auth', requires=basic_authentication)
def basic_auth_api_call(user: hug.directives.user):
    """Testing whether authenticated calls work"""
    return f'Successfully authenticated with user: {user}'


@hug.get('/user')
def list_users():
    session = Session()
    return itertoolz.concat(session.query(User.name).all())


@hug.delete('/user/{username}', requires=basic_authentication)
def del_user(username: str, response):
    session = Session()
    user: User = session.query(User).filter(User.name == username).first()
    if not user:
        logger.warning("User %s not found", username)
        response.status = falcon.HTTP_404
        return
    session.delete(user)
    session.commit()


###
# Notes stuff
###


@hug.get('/user/{username}/notes')
def list_notes(username: str, response):
    session = Session()
    user: User = session.query(User).filter(User.name == username).first()
    if not user:
        logger.warning("User %s not found", username)
        response.status = falcon.HTTP_404
        return

    return {x.id: x.text for x in user.notes}


@hug.post('/note', requires=basic_authentication)
def new_note(user: hug.directives.user, text: str, response):
    session = Session()
    note = Notes(text=text, owner_id=user.id)
    session.add(note)
    session.commit()
    response.status = falcon.HTTP_201
    response._headers['Location'] = f'/note/{note.id}'
    return {'id': note.id}


@hug.put('/note/{id}', requires=basic_authentication)
def update_note(user: hug.directives.user, id: int, text: str, response):
    session = Session()
    note: Notes = session.query(Notes).filter(Notes.id == id).first()
    if not note:
        logger.warning(f"Note with id {id} not found")
        note = Notes(text=text, owner_id=user.id)
        session.add(note)
        session.commit()
        response.status = falcon.HTTP_201
        response._headers['Location'] = f'/note/{id}'
        return {'id': note.id}

    if note.owner_id != user.id:
        logger.warning(f"Note with id {id} not owned by {user.name}")
        response.status = falcon.HTTP_401
        return

    note.text = text
    session.commit()
    return {'id': note.id}


@hug.delete('/note/{id}', requires=basic_authentication)
def delete_note(user: hug.directives.user, id: str, response):
    session = Session()
    note: Notes = session.query(Notes).filter(Notes.id == id).first()
    if not note:
        logger.warning(f"Note with id {id} not found")
        response.status = falcon.HTTP_404
        return

    if note.owner_id != user.id:
        logger.warning(f"Note with id {id} not owned by {user.name}")
        response.status = falcon.HTTP_401
        return

    session.delete(note)
    session.commit()


@hug.get('/note/{id}')
def get_note(id: str, response):
    session = Session()
    note: Notes = session.query(Notes).filter(Notes.id == id).first()
    if not note:
        logger.warning(f"Note with id {id} not found")
        response.status = falcon.HTTP_404
        return
    return note.text


if __name__ == '__main__':
    add_user.interface.cli()

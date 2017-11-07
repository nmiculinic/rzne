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
        iterations=100000,
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


@hug.cli()
@hug.post('/user/{username}', requires=basic_authentication)
def add_user(username, password):
    """
    CLI Parameter to add a user to the database
    :param username:
    :param password:
    :return: JSON status output
    """

    salt = hashlib.sha512(str(os.urandom(64)).encode('utf-8')).digest()
    password_hash = hash_password(password, salt)
    user = User(
        name=username,
        salt=salt,
        hash=password_hash,
    )
    session = Session()
    session.add(user)
    session.commit()

    return {'result': 'success', 'eid': user.id, 'user_created': user}


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


@hug.get('/users/{username}/notes')
def list_notes(username: str, response):
    session = Session()
    user: User = session.query(User).filter(User.name == username).first()
    if not user:
        logger.warning("User %s not found", username)
        response.status = falcon.HTTP_404
        return

    return user.notes


@hug.post('/notes', requires=basic_authentication)
def new_note(user: hug.directives.user, text: str, response):
    session = Session()
    note = Notes(text=text, owner_id=user.id)
    session.add(note)
    session.commit()
    return {'id': note.id}


@hug.put('/notes/{id}', requires=basic_authentication)
def update_note(user: hug.directives.user, id: int, text: str, response):
    session = Session()
    note: Notes = session.query(Notes).filter(Notes.id == id).first()
    if not note:
        logger.warning(f"Note with id {id} not found")
        note = Notes(text=text, owner_id=user.id)
        session.add(note)
        session.commit()
        response.status = falcon.HTTP_201
        return {'id': note.id}

    if note.owner_id != user.id:
        logger.warning(f"Note with id {id} not owned by {user.name}")
        response.status = falcon.HTTP_401
        return

    note.text = text
    session.commit()
    return {'id': note.id}


@hug.delete('/notes/{id}', requires=basic_authentication)
def update_note(user: hug.directives.user, id: str, response):
    session = Session()
    note: Notes = session.query(Notes).filter(Notes.id == id).first()
    if not note:
        logger.warning(f"Note with id {id} not found")
        response.status = falcon.HTTP_404

    if note.owner_id != user.id:
        logger.warning(f"Note with id {id} not owned by {user.name}")
        response.status = falcon.HTTP_401
        return

    session.delete(note)
    session.commit()


if __name__ == '__main__':
    add_user.interface.cli()

import hashlib
import logging
import os

import hug
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
"""
  Helper Methods
"""

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

salt = b'\n\x11\xa5\xdd\x0fq\xf8p=[\xae\xe2V\xde\xd9\xb2'
kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=salt,
    iterations=100000,
    backend=default_backend())


class User(Base):
    __tablename__ = 'users'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String, unique=True)
    salt = sa.Column(sa.BLOB)
    hash = sa.Column(sa.BLOB)

    def __repr__(self):
        return f"<User(name={self.name}, salt={self.salt}, hash={self.hash})>"


engine = create_engine('sqlite:////tmp/foo.db')
Session = sessionmaker(bind=engine)


def hash_password(password, salt):
    """
    Securely hash a password using a provided salt
    :param password:
    :param salt:
    :return: Hex encoded SHA512 hash of provided password
    """
    password = kdf.derive(password.encode("UTF-8"))
    return hashlib.sha512(password + salt).digest()


@hug.cli()
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


if __name__ == '__main__':
    add_user.interface.cli()

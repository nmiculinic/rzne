import hashlib
import logging
import os

import hug
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
engine = create_engine('sqlite:///tmp/foo.db')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
"""
  Helper Methods
"""


class User(Base):
    __tablename__ = 'users'
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String)
    salt = sa.Column(sa.String)
    hash = sa.Column(sa.String)

    def __repr__(self):
        return f"<User(name={self.name}, salt={self.salt}, hash={self.hash})>"


Base.metadata.create_all(engine)


def hash_password(password, salt):
    """
    Securely hash a password using a provided salt
    :param password:
    :param salt:
    :return: Hex encoded SHA512 hash of provided password
    """
    password = str(password).encode('utf-8')
    salt = str(salt).encode('utf-8')
    return hashlib.sha512(password + salt).hexdigest()


@hug.cli()
def authenticate_user(username, password):
    """
    Authenticate a username and password against our database
    :param username:
    :param password:
    :return: authenticated username
    """
    user_model = Query()
    user = engine.get(user_model.username == username)

    if not user:
        logger.warning("User %s not found", username)
        return False

    if user['password'] == hash_password(password, user.get('salt')):
        return user['username']

    return False


basic_authentication = hug.authentication.basic(authenticate_user)


@hug.cli()
def add_user(username, password):
    """
    CLI Parameter to add a user to the database
    :param username:
    :param password:
    :return: JSON status output
    """

    user_model = Query()
    if db.search(user_model.username == username):
        return {'error': 'User {0} already exists'.format(username)}

    salt = hashlib.sha512(str(os.urandom(64)).encode('utf-8')).hexdigest()
    password = hash_password(password, salt)

    user = {
        'username': username,
        'password': password,
        'salt': salt,
    }
    user_id = db.insert(user)

    return {'result': 'success', 'eid': user_id, 'user_created': user}


@hug.get('/api/get_api_key', requires=basic_authentication)
def get_token(authed_user: hug.directives.user):
    """
    Get Job details
    :param authed_user:
    :return:
    """
    user_model = Query()
    user = db.search(user_model.username == authed_user)[0]

    if user:
        out = {'user': user['username'], 'api_key': user['api_key']}
    else:
        # this should never happen
        out = {'error': 'User {0} does not exist'.format(authed_user)}

    return out


# Same thing, but authenticating against an API key
@hug.get(('/api/job', '/api/job/{job_id}/'), requires=api_key_authentication)
def get_job_details(job_id):
    """
    Get Job details
    :param job_id:
    :return:
    """
    job = {'job_id': job_id, 'details': 'Details go here'}

    return job


if __name__ == '__main__':
    add_user.interface.cli()

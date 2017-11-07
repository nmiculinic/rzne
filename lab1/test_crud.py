import logging
import os
import os.path as path
import sys
import unittest
from pprint import PrettyPrinter

import falcon
import hug
from falcon import HTTP_200
from falcon import HTTP_400
from falcon import HTTP_404
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
try:
    from . import crud
except:
    sys.path.append(path.dirname(path.abspath(__file__)))
    import crud

pp = PrettyPrinter()
os.environ["CI"] = "true"


class TestUser(unittest.TestCase):
    def setUp(self):
        crud.engine = create_engine('sqlite://')
        crud.Session = sessionmaker(bind=crud.engine)
        crud.Base.metadata.create_all(crud.engine)

    def test_empty_users(self):
        response = hug.test.get(crud, '/user')
        self.assertEqual(response.status, HTTP_200)
        self.assertEqual(response.data, [])

    def test_single_user(self):
        crud.add_user('test', 'test')
        response = hug.test.get(crud, '/user')
        self.assertEqual(response.status, HTTP_200)
        self.assertEqual(response.data, ['test'])

    def test_unathorized_creation(self):
        response = hug.test.post(crud, '/user/add', {'password': 'add'})
        self.assertEqual(response.status, falcon.HTTP_401)

    def test_REST_user_creation(self):
        crud.add_user('test', 'test')
        response = hug.test.post(
            crud,
            '/user/add', {'password': 'add'},
            headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(response.status, falcon.HTTP_201)

    def test_duplicate_user(self):
        crud.add_user('test', 'test')
        crud.add_user('add', 'test')
        response = hug.test.post(
            crud,
            '/user/add', {'password': 'add'},
            headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(response.status, falcon.HTTP_400)

    def test_delete_user(self):
        crud.add_user('test', 'test')
        crud.add_user('add', 'test')
        response = hug.test.delete(
            crud, '/user/add', headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(response.status, falcon.HTTP_200)

    def test_delete_nonexistent(self):
        crud.add_user('test', 'test')
        response = hug.test.delete(
            crud,
            '/user/addd',
            headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(response.status, falcon.HTTP_404)

    def test_nonexistent_user(self):
        response = hug.test.delete(
            crud,
            '/user/addd',
            headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(response.status, falcon.HTTP_401)

    def test_wrong_pass(self):
        crud.add_user('test', 'test')
        response = hug.test.delete(
            crud,
            '/user/addd',
            headers={
                'Authorization': 'Basic dGVzdDpzc3M='
            })
        self.assertEqual(response.status, falcon.HTTP_401)


class TestNotes(unittest.TestCase):
    def setUp(self):
        crud.engine = create_engine('sqlite://')
        crud.Session = sessionmaker(bind=crud.engine)
        crud.Base.metadata.create_all(crud.engine)

    def test_invalid_user_notes(self):
        response: falcon.Response = hug.test.get(crud, '/user/ss/notes')
        self.assertEqual(response.status, falcon.HTTP_404)

    def test_empty_notes(self):
        crud.add_user('test', 'test')
        resp = hug.test.get(crud, '/user/test/notes')
        self.assertEqual(resp.status, falcon.HTTP_200)
        self.assertEqual(resp.data, {})

    def test_nonexistent_note(self):
        resp = hug.test.get(crud, '/note/5')
        self.assertEqual(resp.status, falcon.HTTP_404)

    def test_update_nonexistent(self):
        crud.add_user('test', 'test')
        # Create
        resp = hug.test.put(
            crud,
            '/note/1', {'text': "Ja sam mala vjeverica"},
            headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(resp.status, falcon.HTTP_201)

        resp = hug.test.get(crud, f'/note/1')
        self.assertEqual(resp.status, falcon.HTTP_200)
        self.assertEqual(resp.data, "Ja sam mala vjeverica")

    def test_access_others_note(self):
        crud.add_user('test', 'test')
        crud.add_user('asd', 'test')
        # Create
        resp = hug.test.put(
            crud,
            '/note/1', {'text': "asd is happy"},
            headers={
                'Authorization': 'Basic YXNkOnRlc3Q='
            })
        self.assertEqual(resp.status, falcon.HTTP_201)

        resp = hug.test.get(crud, f'/note/1')
        self.assertEqual(resp.status, falcon.HTTP_200)
        self.assertEqual(resp.data, "asd is happy")

        # Try update others note
        resp = hug.test.put(
            crud,
            '/note/1', {'text': "Ja sam mala vjeverica"},
            headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(resp.status, falcon.HTTP_401)
        resp = hug.test.get(crud, f'/note/1')
        self.assertEqual(resp.status, falcon.HTTP_200)
        self.assertEqual(resp.data, "asd is happy")

        # Try deleting other's note
        resp = hug.test.delete(
            crud, '/note/1', headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(resp.status, falcon.HTTP_401)
        resp = hug.test.get(crud, f'/note/1')
        self.assertEqual(resp.status, falcon.HTTP_200)
        self.assertEqual(resp.data, "asd is happy")

    def test_delete_missing_note(self):
        crud.add_user('test', 'test')
        resp = hug.test.delete(
            crud, '/note/5', headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(resp.status, falcon.HTTP_404)

    def test_get_missing_note(self):
        resp = hug.test.get(crud, '/note/5')
        self.assertEqual(resp.status, falcon.HTTP_404)

    def test_note_lifecycle(self):
        crud.add_user('test', 'test')

        # Create
        resp = hug.test.post(
            crud,
            '/note', {'text': "Ja sam mala vjeverica"},
            headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(resp.status, falcon.HTTP_201)
        self.assertIn(('location', f'/note/{resp.data["id"]}'), resp.headers)

        id = resp.data['id']
        resp = hug.test.get(crud, '/user/test/notes')
        self.assertEqual(resp.data, {str(id): "Ja sam mala vjeverica"})
        self.assertEqual(resp.status, falcon.HTTP_200)
        # Read
        resp = hug.test.get(crud, f'/note/{id}')
        self.assertEqual(resp.status, falcon.HTTP_200)
        self.assertEqual(resp.data, "Ja sam mala vjeverica")

        # Update
        resp = hug.test.put(
            crud,
            f'/note/{id}', {'text': "Vj2"},
            headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(resp.status, falcon.HTTP_200)
        # Read again
        resp = hug.test.get(crud, f'/note/{id}')
        self.assertEqual(resp.status, falcon.HTTP_200)
        self.assertEqual(resp.data, "Vj2")

        # Delete
        resp = hug.test.delete(
            crud,
            f'/note/{id}',
            headers={
                'Authorization': 'Basic dGVzdDp0ZXN0'
            })
        self.assertEqual(resp.status, falcon.HTTP_200)

        resp = hug.test.get(crud, f'/note/{id}')
        self.assertEqual(resp.status, falcon.HTTP_404)

        resp = hug.test.get(crud, '/user/test/notes')
        self.assertEqual(resp.data, {})
        self.assertEqual(resp.status, falcon.HTTP_200)


if __name__ == "__main__":
    logging.basicConfig(
        format=
        '%(asctime)s [%(levelname)s]{%(filename)s:%(lineno)d}: %(message)s',
        level=logging.DEBUG)
    unittest.main()

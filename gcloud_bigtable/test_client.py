# Copyright 2015 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import unittest2


class Test__project_id_from_environment(unittest2.TestCase):

    def _callFUT(self):
        from gcloud_bigtable.client import _project_id_from_environment
        return _project_id_from_environment()

    def test_it(self):
        from gcloud_bigtable._testing import _MockWithAttachedMethods
        from gcloud_bigtable._testing import _Monkey
        from gcloud_bigtable import client as MUT

        fake_project_id = object()
        mock_os = _MockWithAttachedMethods(fake_project_id)
        with _Monkey(MUT, os=mock_os):
            result = self._callFUT()

        self.assertTrue(result is fake_project_id)
        self.assertEqual(mock_os._called,
                         [('getenv', (MUT.PROJECT_ENV_VAR,), {})])


class Test__project_id_from_app_engine(unittest2.TestCase):

    def _callFUT(self):
        from gcloud_bigtable.client import _project_id_from_app_engine
        return _project_id_from_app_engine()

    def test_without_app_engine(self):
        from gcloud_bigtable._testing import _Monkey
        from gcloud_bigtable import client as MUT

        with _Monkey(MUT, app_identity=None):
            result = self._callFUT()

        self.assertEqual(result, None)

    def test_with_app_engine(self):
        from gcloud_bigtable._testing import _MockWithAttachedMethods
        from gcloud_bigtable._testing import _Monkey
        from gcloud_bigtable import client as MUT

        fake_project_id = object()
        mock_app_identity = _MockWithAttachedMethods(fake_project_id)
        with _Monkey(MUT, app_identity=mock_app_identity):
            result = self._callFUT()

        self.assertTrue(result is fake_project_id)
        self.assertEqual(mock_app_identity._called,
                         [('get_application_id', (), {})])


class Test__project_id_from_compute_engine(unittest2.TestCase):

    def _callFUT(self):
        from gcloud_bigtable.client import _project_id_from_compute_engine
        return _project_id_from_compute_engine()

    @staticmethod
    def _make_http_connection_response(status_code, read_result,
                                       raise_socket_err=False):
        import socket

        class Response(object):
            status = status_code

            @staticmethod
            def read():
                if raise_socket_err:
                    raise socket.error('Failed')
                else:
                    return read_result
        return Response

    @staticmethod
    def _make_fake_six_module(mock_http_client):
        class MockSix(object):
            class moves(object):
                http_client = mock_http_client
        return MockSix

    def _helper(self, status, raise_socket_err=False):
        from gcloud_bigtable._testing import _MockWithAttachedMethods
        from gcloud_bigtable._testing import _Monkey
        from gcloud_bigtable import client as MUT

        fake_project_id = object()
        response = self._make_http_connection_response(
            status, fake_project_id, raise_socket_err=raise_socket_err)
        # The connection does the bulk of the work.
        mock_connection = _MockWithAttachedMethods(None, response, None)
        # The http_client module holds the connection constructor.
        mock_http_client = _MockWithAttachedMethods(mock_connection)
        # We need to put the client in place of it's location in six.
        mock_six = self._make_fake_six_module(mock_http_client)

        with _Monkey(MUT, six=mock_six):
            result = self._callFUT()

        if status == 200 and not raise_socket_err:
            self.assertEqual(result, fake_project_id)
        else:
            self.assertEqual(result, None)

        self.assertEqual(mock_connection._called, [
            (
                'request',
                ('GET', '/computeMetadata/v1/project/project-id'),
                {'headers': {'Metadata-Flavor': 'Google'}},
            ),
            (
                'getresponse',
                (),
                {},
            ),
            (
                'close',
                (),
                {},
            ),
        ])
        self.assertEqual(mock_http_client._called, [
            (
                'HTTPConnection',
                ('169.254.169.254',),
                {'timeout': 0.1},
            ),
        ])

    def test_success(self):
        self._helper(200)

    def test_failed_status(self):
        self._helper(404)

    def test_read_fails_with_socket_error(self):
        self._helper(200, raise_socket_err=True)


class Test__determine_project_id(unittest2.TestCase):

    def _callFUT(self, project_id):
        from gcloud_bigtable.client import _determine_project_id
        return _determine_project_id(project_id)

    def _helper(self, num_mocks_called, mock_output, method_input):
        from gcloud_bigtable._testing import _MockCalled
        from gcloud_bigtable._testing import _Monkey
        from gcloud_bigtable import client as MUT

        mock_project_id_from_environment = _MockCalled(None)
        mock_project_id_from_app_engine = _MockCalled(None)
        mock_project_id_from_compute_engine = _MockCalled(None)

        monkey_kwargs = {
            '_project_id_from_environment': mock_project_id_from_environment,
            '_project_id_from_app_engine': mock_project_id_from_app_engine,
            '_project_id_from_compute_engine': (
                mock_project_id_from_compute_engine),
        }
        # Need the mocks in order they are called, so we can
        # access them based on `num_mocks_called`.
        mocks = [
            mock_project_id_from_environment,
            mock_project_id_from_app_engine,
            mock_project_id_from_compute_engine,
        ]
        mocks[num_mocks_called - 1].result = mock_output

        with _Monkey(MUT, **monkey_kwargs):
            if num_mocks_called == 3 and mock_output is None:
                with self.assertRaises(EnvironmentError):
                    self._callFUT(method_input)
            else:
                result = self._callFUT(method_input)
                self.assertEqual(result, method_input or mock_output)

        # Make sure our mocks were called with no arguments.
        for mock in mocks[:num_mocks_called]:
            mock.check_called(self, [()])
        for mock in mocks[num_mocks_called:]:
            mock.check_called(self, [])

    def test_fail_to_infer(self):
        self._helper(num_mocks_called=3, mock_output=None,
                     method_input=None)

    def test_with_explicit_value(self):
        self._helper(num_mocks_called=0, mock_output=None,
                     method_input='PROJECT_ID')

    def test_from_environment(self):
        self._helper(num_mocks_called=1, mock_output='PROJECT_ID',
                     method_input=None)

    def test_from_app_engine(self):
        self._helper(num_mocks_called=2, mock_output='PROJECT_ID',
                     method_input=None)

    def test_from_compute_engine(self):
        self._helper(num_mocks_called=3, mock_output='PROJECT_ID',
                     method_input=None)


class TestClient(unittest2.TestCase):

    def _getTargetClass(self):
        from gcloud_bigtable.client import Client
        return Client

    def _makeOne(self, *args, **kwargs):
        return self._getTargetClass()(*args, **kwargs)

    def _constructor_test_helper(self, expected_scopes, project_id=None,
                                 admin=False, read_only=False):
        from gcloud_bigtable._testing import _MockCalled
        from gcloud_bigtable._testing import _MockWithAttachedMethods
        from gcloud_bigtable._testing import _Monkey
        from gcloud_bigtable import client as MUT

        scoped_creds = object()
        credentials = _MockWithAttachedMethods(scoped_creds)
        determined_project_id = object()
        mock_determine_project_id = _MockCalled(determined_project_id)
        with _Monkey(MUT, _determine_project_id=mock_determine_project_id):
            client = self._makeOne(credentials, project_id=project_id,
                                   admin=admin, read_only=read_only)

        self.assertTrue(client._credentials is scoped_creds)
        self.assertEqual(credentials._called, [
            ('create_scoped', (expected_scopes,), {}),
        ])
        self.assertTrue(client._project_id is determined_project_id)
        mock_determine_project_id.check_called(self, [(project_id,)])

    def test_constructor_default(self):
        from gcloud_bigtable import client as MUT
        expected_scopes = [MUT.DATA_SCOPE]
        self._constructor_test_helper(expected_scopes)

    def test_constructor_with_explicit_project_id(self):
        from gcloud_bigtable import client as MUT
        expected_scopes = [MUT.DATA_SCOPE]
        project_id = 'PROJECT_ID'
        self._constructor_test_helper(expected_scopes, project_id=project_id)

    def test_constructor_with_admin(self):
        from gcloud_bigtable import client as MUT
        expected_scopes = [MUT.DATA_SCOPE, MUT.ADMIN_SCOPE]
        self._constructor_test_helper(expected_scopes, admin=True)

    def test_constructor_with_read_only(self):
        from gcloud_bigtable import client as MUT
        expected_scopes = [MUT.READ_ONLY_SCOPE]
        self._constructor_test_helper(expected_scopes, read_only=True)

    def test_constructor_both_admin_and_read_only(self):
        with self.assertRaises(ValueError):
            self._makeOne(None, admin=True, read_only=True)

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

"""User friendly container for Google Cloud Bigtable Cluster."""


import re

from gcloud_bigtable._generated import bigtable_cluster_data_pb2 as data_pb2
from gcloud_bigtable._generated import (
    bigtable_cluster_service_messages_pb2 as messages_pb2)
from gcloud_bigtable._generated import (
    bigtable_table_service_messages_pb2 as table_messages_pb2)
from gcloud_bigtable._generated import operations_pb2
from gcloud_bigtable._helpers import _parse_pb_any_to_native
from gcloud_bigtable._helpers import _pb_timestamp_to_datetime
from gcloud_bigtable.table import Table


_CLUSTER_NAME_RE = re.compile(r'^projects/(?P<project>[^/]+)/'
                              r'zones/(?P<zone>[^/]+)/clusters/'
                              r'(?P<cluster_id>[a-z][-a-z0-9]*)$')
_OPERATION_NAME_RE = re.compile(r'^operations/projects/([^/]+)/zones/([^/]+)/'
                                r'clusters/([a-z][-a-z0-9]*)/operations/'
                                r'(?P<operation_id>\d+)$')


def _get_pb_property_value(message_pb, property_name):
    """Return a message field value.

    :type message_pb: :class:`google.protobuf.message.Message`
    :param message_pb: The message to check for ``property_name``.

    :type property_name: str
    :param property_name: The property value to check against.

    :rtype: object
    :returns: The value of ``property_name`` set on ``message_pb``.
    :raises: :class:`ValueError <exceptions.ValueError>` if the result returned
             from the ``message_pb`` does not contain the ``property_name``
             value.
    """
    # Make sure `property_name` is set on the response.
    # NOTE: As of proto3, HasField() only works for message fields, not for
    #       singular (non-message) fields.
    all_fields = set([field.name for field in message_pb._fields])
    if property_name not in all_fields:
        raise ValueError('Message does not contain %s.' % (property_name,))
    return getattr(message_pb, property_name)


def _prepare_create_request(cluster):
    """Creates a protobuf request for a CreateCluster request.

    :type cluster: :class:`Cluster`
    :param cluster: The cluster to be created.

    :rtype: :class:`.messages_pb2.CreateClusterRequest`
    :returns: The CreateCluster request object containing the cluster info.
    """
    zone_full_name = ('projects/' + cluster.project +
                      '/zones/' + cluster.zone)
    return messages_pb2.CreateClusterRequest(
        name=zone_full_name,
        cluster_id=cluster.cluster_id,
        cluster=data_pb2.Cluster(
            display_name=cluster.display_name,
            serve_nodes=cluster.serve_nodes,
        ),
    )


def _process_operation(operation_pb):
    """Processes a create protobuf response.

    :type operation_pb: :class:`operations_pb2.Operation`
    :param operation_pb: The long-running operation response from a
                         Create/Update/Undelete cluster request.

    :rtype: tuple
    :returns: A pair of an integer and datetime stamp. The integer is the ID
              of the operation (``operation_id``) and the timestamp when
              the create operation began (``operation_begin``).
    :raises: :class:`ValueError <exceptions.ValueError>` if the operation name
             doesn't match the :data:`_OPERATION_NAME_RE` regex.
    """
    match = _OPERATION_NAME_RE.match(operation_pb.name)
    if match is None:
        raise ValueError('Cluster create operation name was not in the '
                         'expected format.', operation_pb.name)
    operation_id = int(match.group('operation_id'))

    request_metadata = _parse_pb_any_to_native(operation_pb.metadata)
    operation_begin = _pb_timestamp_to_datetime(
        request_metadata.request_time)

    return operation_id, operation_begin


class Operation(object):
    """Representation of a Google API Long-Running Operation.

    In particular, these will be the result of operations on
    clusters using the Cloud Bigtable API.

    :type op_type: str
    :param op_type: The type of operation being performed. Expect
                    ``create``, ``update`` or ``undelete``.

    :type op_id: int
    :param op_id: The ID of the operation.

    :type begin: :class:`datetime.datetime`
    :param begin: The time when the operation was started.

    :type cluster: :class:`Cluster`
    :param cluster: The cluster that created the operation.
    """

    def __init__(self, op_type, op_id, begin, cluster=None):
        self.op_type = op_type
        self.op_id = op_id
        self.begin = begin
        self._cluster = cluster
        self._complete = False

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return (other.op_type == self.op_type and
                other.op_id == self.op_id and
                other.begin == self.begin and
                other._cluster == self._cluster and
                other._complete == self._complete)

    def __ne__(self, other):
        return not self.__eq__(other)

    def finished(self, timeout_seconds=None):
        """Check if the operation has finished.

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on
                                cluster.

        :rtype: bool
        :returns: A boolean indicating if the current operation has completed.
        :raises: :class:`ValueError <exceptions.ValueError>` if the operation
                 has already completed.
        """
        if self._complete:
            raise ValueError('The operation has completed.')

        operation_name = ('operations/' + self._cluster.name +
                          '/operations/%d' % (self.op_id,))
        request_pb = operations_pb2.GetOperationRequest(name=operation_name)
        timeout_seconds = timeout_seconds or self._cluster.timeout_seconds
        # We expact a `._generated.operations_pb2.Operation`.
        operation_pb = self._cluster._client._operations_stub.GetOperation(
            request_pb, timeout_seconds)

        if operation_pb.done:
            self._complete = True
            return True
        else:
            return False


class Cluster(object):
    """Representation of a Google Cloud Bigtable Cluster.

    We can use a :class:`Cluster` to:

    * :meth:`reload` itself
    * :meth:`create` itself
    * :meth:`update` itself
    * :meth:`delete` itself
    * :meth:`undelete` itself

    .. note::

        For now, we leave out the ``default_storage_type`` (an enum)
        which if not sent will end up as :data:`.data_pb2.STORAGE_SSD`.

    :type zone: str
    :param zone: The name of the zone where the cluster resides.

    :type cluster_id: str
    :param cluster_id: The ID of the cluster.

    :type client: :class:`.client.Client`
    :param client: The client that owns the cluster. Provides
                   authorization and a project ID.

    :type display_name: str
    :param display_name: (Optional) The display name for the cluster in the
                         Cloud Console UI. (Must be between 4 and 30
                         characters.) If this value is not set in the
                         constructor, will fall back to the cluster ID.

    :type serve_nodes: int
    :param serve_nodes: (Optional) The number of nodes in the cluster.
                        Defaults to 3.
    """

    def __init__(self, zone, cluster_id, client,
                 display_name=None, serve_nodes=3):
        self.zone = zone
        self.cluster_id = cluster_id
        self.display_name = display_name or cluster_id
        self.serve_nodes = serve_nodes
        self._client = client

    def table(self, table_id):
        """Factory to create a table associated with this cluster.

        :type table_id: str
        :param table_id: The ID of the table.

        :rtype: :class:`Table <gcloud_bigtable.table.Table>`
        :returns: The table owned by this cluster.
        """
        return Table(table_id, self)

    def _update_from_pb(self, cluster_pb):
        self.display_name = _get_pb_property_value(cluster_pb, 'display_name')
        self.serve_nodes = _get_pb_property_value(cluster_pb, 'serve_nodes')

    @classmethod
    def from_pb(cls, cluster_pb, client):
        """Creates a cluster instance from a protobuf.

        :type cluster_pb: :class:`bigtable_cluster_data_pb2.Cluster`
        :param cluster_pb: A cluster protobuf object.

        :type client: :class:`.client.Client`
        :param client: The client that owns the cluster.

        :rtype: :class:`Cluster`
        :returns: The cluster parsed from the protobuf response.
        :raises: :class:`ValueError <exceptions.ValueError>` if the cluster
                 name does not match :data:`_CLUSTER_NAME_RE` or if the parsed
                 project ID does not match the project ID on the client.
        """
        match = _CLUSTER_NAME_RE.match(cluster_pb.name)
        if match is None:
            raise ValueError('Cluster protobuf name was not in the '
                             'expected format.', cluster_pb.name)
        if match.group('project') != client.project:
            raise ValueError('Project ID on cluster does not match the '
                             'project ID on the client')

        result = cls(match.group('zone'), match.group('cluster_id'), client)
        result._update_from_pb(cluster_pb)
        return result

    def copy(self):
        """Make a copy of this cluster.

        Copies the local data stored as simple types but does not copy the
        current state of any operations with the Cloud Bigtable API. Also
        copies the client attached to this instance.

        :rtype: :class:`.Cluster`
        :returns: A copy of the current cluster.
        """
        new_client = self.client.copy()
        return self.__class__(self.zone, self.cluster_id, new_client,
                              display_name=self.display_name,
                              serve_nodes=self.serve_nodes)

    @property
    def client(self):
        """Getter for cluster's client.

        :rtype: :class:`.client.Client`
        :returns: The client stored on the cluster.
        """
        return self._client

    @property
    def project(self):
        """Getter for cluster's project ID.

        :rtype: str
        :returns: The project ID for the cluster (is stored on the client).
        """
        return self._client.project

    @property
    def timeout_seconds(self):
        """Getter for cluster's default timeout seconds.

        :rtype: int
        :returns: The timeout seconds default stored on the cluster's client.
        """
        return self._client.timeout_seconds

    @property
    def name(self):
        """Cluster name used in requests.

        .. note::
          This property will not change if ``zone`` and ``cluster_id`` do not,
          but the return value is not cached.

        The cluster name is of the form

            ``"projects/{project}/zones/{zone}/clusters/{cluster_id}"``

        :rtype: str
        :returns: The cluster name.
        """
        return (self.client.project_name + '/zones/' + self.zone +
                '/clusters/' + self.cluster_id)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        # NOTE: This does not compare the configuration values, such as
        #       the serve_nodes or display_name. Instead, it only compares
        #       identifying values zone, cluster ID and client. This is
        #       intentional, since the same cluster can be in different states
        #       if not synchronized. Clusters with similar zone/cluster
        #       settings but different clients can't be used in the same way.
        return (other.zone == self.zone and
                other.cluster_id == self.cluster_id and
                other.client == self.client)

    def __ne__(self, other):
        return not self.__eq__(other)

    def reload(self, timeout_seconds=None):
        """Reload the metadata for this cluster.

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on
                                cluster.
        """
        request_pb = messages_pb2.GetClusterRequest(name=self.name)
        timeout_seconds = timeout_seconds or self.timeout_seconds
        # We expect a `._generated.bigtable_cluster_data_pb2.Cluster`.
        cluster_pb = self.client._cluster_stub.GetCluster(request_pb,
                                                          timeout_seconds)

        # NOTE: _update_from_pb does not check that the project, zone and
        #       cluster ID on the response match the request.
        self._update_from_pb(cluster_pb)

    def create(self, timeout_seconds=None):
        """Create this cluster.

        .. note::

            Uses the ``project``, ``zone`` and ``cluster_id`` on the current
            :class:`Cluster` in addition to the ``display_name`` and
            ``serve_nodes``. If you'd like to change them before creating,
            reset the values via

            .. code:: python

                cluster.display_name = 'New display name'
                cluster.cluster_id = 'i-changed-my-mind'

            before calling :meth:`create`.

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on
                                cluster.

        :rtype: :class:`Operation`
        :returns: The long-running operation corresponding to the
                  create operation.
        """
        request_pb = _prepare_create_request(self)
        timeout_seconds = timeout_seconds or self.timeout_seconds
        # We expect an `operations_pb2.Operation`.
        cluster_pb = self.client._cluster_stub.CreateCluster(
            request_pb, timeout_seconds)

        op_id, op_begin = _process_operation(cluster_pb.current_operation)
        return Operation('create', op_id, op_begin, cluster=self)

    def update(self, timeout_seconds=None):
        """Update this cluster.

        .. note::

            Updates the ``display_name`` and ``serve_nodes``. If you'd like to
            change them before updating, reset the values via

            .. code:: python

                cluster.display_name = 'New display name'
                cluster.serve_nodes = 3

            before calling :meth:`update`.

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on
                                cluster.

        :rtype: :class:`Operation`
        :returns: The long-running operation corresponding to the
                  update operation.
        """
        request_pb = data_pb2.Cluster(
            name=self.name,
            display_name=self.display_name,
            serve_nodes=self.serve_nodes,
        )
        timeout_seconds = timeout_seconds or self.timeout_seconds
        # We expect a `._generated.bigtable_cluster_data_pb2.Cluster`.
        cluster_pb = self.client._cluster_stub.UpdateCluster(
            request_pb, timeout_seconds)

        op_id, op_begin = _process_operation(cluster_pb.current_operation)
        return Operation('update', op_id, op_begin, cluster=self)

    def delete(self, timeout_seconds=None):
        """Delete this cluster.

        Marks a cluster and all of its tables for permanent deletion in 7 days.

        Immediately upon completion of the request:

        * Billing will cease for all of the cluster's reserved resources.
        * The cluster's ``delete_time`` field will be set 7 days in the future.

        Soon afterward:

        * All tables within the cluster will become unavailable.

        Prior to the cluster's ``delete_time``:

        * The cluster can be recovered with a call to ``UndeleteCluster``.
        * All other attempts to modify or delete the cluster will be rejected.

        At the cluster's ``delete_time``:

        * The cluster and **all of its tables** will immediately and
          irrevocably disappear from the API, and their data will be
          permanently deleted.

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on
                                cluster.
        """
        request_pb = messages_pb2.DeleteClusterRequest(name=self.name)
        timeout_seconds = timeout_seconds or self.timeout_seconds
        # We expect a `._generated.empty_pb2.Empty`
        self.client._cluster_stub.DeleteCluster(request_pb, timeout_seconds)

    def undelete(self, timeout_seconds=None):
        """Undelete this cluster.

        Cancels the scheduled deletion of an cluster and begins preparing it to
        resume serving. The returned operation will also be embedded as the
        cluster's ``current_operation``.

        Immediately upon completion of this request:

        * The cluster's ``delete_time`` field will be unset, protecting it from
          automatic deletion.

        Until completion of the returned operation:

        * The operation cannot be cancelled.

        Upon completion of the returned operation:

        * Billing for the cluster's resources will resume.
        * All tables within the cluster will be available.

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on
                                cluster.

        :rtype: :class:`Operation`
        :returns: The long-running operation corresponding to the
                  undelete operation.
        """
        request_pb = messages_pb2.UndeleteClusterRequest(name=self.name)
        timeout_seconds = timeout_seconds or self.timeout_seconds
        # We expect a `._generated.operations_pb2.Operation`
        operation_pb2 = self.client._cluster_stub.UndeleteCluster(
            request_pb, timeout_seconds)

        op_id, op_begin = _process_operation(operation_pb2)
        return Operation('undelete', op_id, op_begin, cluster=self)

    def list_tables(self, timeout_seconds=None):
        """List the tables in this cluster.

        :type timeout_seconds: int
        :param timeout_seconds: Number of seconds for request time-out.
                                If not passed, defaults to value set on
                                cluster.

        :rtype: list of :class:`Table <gcloud_bigtable.table.Table>`
        :returns: The list of tables owned by the cluster.
        :raises: :class:`ValueError <exceptions.ValueError>` if one of the
                 returned tables has a name that is not of the expected format.
        """
        request_pb = table_messages_pb2.ListTablesRequest(name=self.name)
        timeout_seconds = timeout_seconds or self.timeout_seconds
        # We expect a `table_messages_pb2.ListTablesResponse`
        table_list_pb = self.client._table_stub.ListTables(request_pb,
                                                           timeout_seconds)

        result = []
        for table_pb in table_list_pb.tables:
            table_prefix = self.name + '/tables/'
            if not table_pb.name.startswith(table_prefix):
                raise ValueError('Table name %s not of expected format' % (
                    table_pb.name,))
            table_id = table_pb.name[len(table_prefix):]
            result.append(self.table(table_id))

        return result

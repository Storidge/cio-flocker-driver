"""
A CIO implementation of the ``IBlockDeviceAPI``.
"""

from subprocess import check_output
import threading
import time
import logging
from uuid import UUID

from bitmath import Byte, GiB
from boto.utils import get_instance_metadata

from pyrsistent import PRecord, field, pset, pmap
from zope.interface import implementer
from twisted.python.filepath import FilePath

from eliot import Message

from flocker.node.agents.blockdevice import (
    IBlockDeviceAPI, BlockDeviceVolume, UnknownVolume, AlreadyAttachedVolume,
    UnattachedVolume,
)

DATASET_ID_LABEL = u'flocker-dataset-id'
METADATA_VERSION_LABEL = u'flocker-metadata-version'
CLUSTER_ID_LABEL = u'flocker-cluster-id'

class EliotLogHandler(logging.Handler):
    _to_log = {"Method", "Path", "Params"}

    def emit(self, record):
        fields = vars(record)
        # Only log certain things.  The log is massively too verbose
        # otherwise.
        if fields.get("msg", ":").split(":")[0] in self._to_log:
            Message.new(
                message_type=BOTO_LOG_HEADER, **fields
            ).write()


class AttachedUnexpectedDevice(Exception):
    """
    A volume was attached to a device other than the one we expected.

    :ivar str _template: A native string giving the template into which to
        format attributes for the string representation.
    """
    _template = "AttachedUnexpectedDevice(requested={!r}, discovered={!r})"

    def __init__(self, requested, discovered):
        """
        :param FilePath requested: The requested device name.
        :param FilePath discovered: The device which was discovered on the
            system.
        """
        self.requested = requested
        self.discovered = discovered

    def __str__(self):
        return self._template.format(
            self.requested.path, self.discovered.path,
        )

    __repr__ = __str__


def cio_client(region, zone, access_key_id, secret_access_key):
    """
    Establish connection to CIO storage backend.

    :param str region: The name of the CIO region to connect to.
    :param str zone: The zone for the CIO region to connect to.

    :return: An ``_EC2`` giving information about EC2 client connection
        and EC2 instance zone.
    """
    return


def _blockdevicevolume_from_cio_volume(cio_volume):
    """
    Helper function to convert Volume information from
    CIO format to Flocker block device format.

    :param TODO identify CIO volume type.

    :return: Input volume in BlockDeviceVolume format.
    """
    return BlockDeviceVolume(
        blockdevice_id=unicode(cio_volume.id),
        size=int(GiB(ebs_volume.size).to_Byte().value),
        attached_to=cio_volume.attach_data.instance_id,
        dataset_id=UUID(cio_volume.tags[DATASET_ID_LABEL])
    )


def _is_cluster_volume(cluster_id, cio_volume):
    """
    Helper function to check if given volume belongs to
    given cluster.

    :param UUID cluster_id: UUID of Flocker cluster to check for
        membership.
    :param TODO identify CIO volume type: CIO volume to check for
        input cluster membership.

    :return bool: True if input volume belongs to input
        Flocker cluster. False otherwise.
    """
    actual_cluster_id = cio_volume.tags.get(CLUSTER_ID_LABEL)
    if actual_cluster_id is not None:
        actual_cluster_id = UUID(actual_cluster_id)
        if actual_cluster_id == cluster_id:
            return True
    return False


@implementer(IBlockDeviceAPI)
class CIOBlockDeviceAPI(object):
    """
    A CIO implementation of ``IBlockDeviceAPI`` which creates
    block devices in a CIO storage cluster.
    """
    def __init__(self, cluster_id):
        """
        Initialize CIO block device API instance.

        :param UUID cluster_id: UUID of cluster for this
            API instance.
        """
        self.cluster_id = cluster_id
        self.lock = threading.Lock()

    def allocation_unit(self):
        """
        Return a fixed allocation_unit for now; one which we observe
        to work on AWS.
        """
        return int(GiB(8).to_Byte().value)

    def compute_instance_id(self):
        """
        Look up the compute instance ID for this node.
        """
        # TODO: Please update the compute node identifier below so
        # so that CIO driver can work correctly on non-EC2 compute
        # nodes.
        return get_instance_metadata()['instance-id'].decode("ascii")

    def _get_cio_volume(self, blockdevice_id):
        """
        Lookup CIO Volume information for a given blockdevice_id.

        :param unicode blockdevice_id: ID of a blockdevice that needs lookup.

        :returns: TODO: CIO volume format for the input id.

        :raise UnknownVolume: If no volume with a matching identifier can be
             found.
        """
        # TODO: please replace below with CIO command line
        # all_volumes = self.connection.get_all_volumes(
        #    volume_ids=[blockdevice_id])
        # TODO: please generate UnknownVolume exception
        # END TODO

        for volume in all_volumes:
            if volume.id == blockdevice_id:
                return volume
        raise UnknownVolume(blockdevice_id)


    def create_volume(self, dataset_id, size):
        """
        Create a volume on CIO. Store Flocker-specific
        {metadata version, cluster id, dataset id} for the volume
        as volume tag data.
        """
        # TODO: please replace below with CIO callout.
        # requested_volume = self.connection.create_volume(
        #    size=int(Byte(size).to_GiB().value), zone=self.zone)
        # END TODO

        # Sample create command:
        # 'cio vdadd –c 25 –l 2 –t ssd –i 1000 2000 '
        # Create vdisk of size 25 GB, redundancy 2, of type SSD,
        # min IOPS 1000, max IOPS 2000.

        # TODO: please parameterize hardcoded redundancy, min IOPS,
        # max IOPS.
        redundancy = 2
        min_iops = 1000
        max_iops = 2000
        command = [b"/usr/bin/cio", b"-c", size, b"-l", 2b"--bytes",
               b"--output", b"SIZE", device_name]

        # Stamp created volume with Flocker-specific tags.
        metadata = {
            METADATA_VERSION_LABEL: '1',
            CLUSTER_ID_LABEL: unicode(self.cluster_id),
            DATASET_ID_LABEL: unicode(dataset_id),
        }
        # TODO: please replace below with CIO call to add metadata
        # to created volume.
        # self.connection.create_tags([requested_volume.id],
        #                            metadata)
        # END TODO

        # Return created volume in BlockDeviceVolume format.
        return _blockdevicevolume_from_cio_volume(requested_volume)

    def list_volumes(self):
        """
        Return all volumes that belong to this Flocker cluster.
        """
        volumes = []
        # TODO: Please replace below call with CIO command.
        # for ebs_volume in self.connection.get_all_volumes():
        # END TODO
        if _is_cluster_volume(self.cluster_id, cio_volume):
            volumes.append(
                _blockdevicevolume_from_cio_volume(cio_volume)
            )
        return volumes

    def attach_volume(self, blockdevice_id, attach_to):
        """
        Attach an CIO volume to given compute instance.

        :param unicode blockdevice_id: CIO UUID for volume to be attached.
        :param unicode attach_to: Instance id of CIO Compute instance to
            attached the blockdevice to.

        :raises UnknownVolume: If there does not exist a BlockDeviceVolume
            corresponding to the input blockdevice_id.
        :raises AlreadyAttachedVolume: If the input volume is already attached
            to a device.
        :raises AttachedUnexpectedDevice: If the attach operation fails to
            associate the volume with the expected OS device file.  This
            indicates use on an unsupported OS, a misunderstanding of the CIO
            device assignment rules, or some other bug in this implementation.
        """
        cio_volume = self._get_cio_volume(blockdevice_id)
        volume = _blockdevicevolume_from_cio_volume(cio_volume)

        # TODO: Please replace below with CIO commands to raise
        # AlreadyAttachedVolume exception.
        # if (volume.attached_to is not None or
        #       ebs_volume.status != 'available'):
        #   raise AlreadyAttachedVolume(blockdevice_id)
        # END TODO

        # TODO: Please replace below with CIO command to attach volume.
        #  self.connection.attach_volume(blockdevice_id,
        #                                attach_to,
        #                                device)
        # attached_volume = volume.set('attached_to', attach_to)
        # END TODO
 
        # TODO: please make sure attached volume's ``attached_to`` is set.
        # END TODO
        return attached_volume

    def detach_volume(self, blockdevice_id):
        """
        Detach CIO volume identified by blockdevice_id.

        :param unicode blockdevice_id: CIO UUID for volume to be detached.

        :raises UnknownVolume: If there does not exist a BlockDeviceVolume
            corresponding to the input blockdevice_id.
        :raises UnattachedVolume: If the BlockDeviceVolume for the
            blockdevice_id is not currently in use.
        """
        cio_volume = self._get_cio_volume(blockdevice_id)

        # TODO: please get CIO's volume state for attached device.
        # if cio_volume.status != 'in-use':
        #   raise UnattachedVolume(blockdevice_id)
        # END TODO

        # TODO: please use CIO command for detaching volume
        # self.connection.detach_volume(blockdevice_id)
        # END TODO

    def destroy_volume(self, blockdevice_id):
        """
        Destroy CIO volume identified by blockdevice_id.

        :param String blockdevice_id: CIO UUID for volume to be destroyed.

        :raises UnknownVolume: If there does not exist a Flocker cluster
            volume identified by input blockdevice_id.
        :raises Exception: If we failed to destroy Flocker cluster volume
            corresponding to input blockdevice_id.
        """
        cio_volume = self._get_cio_volume(blockdevice_id)

        # TODO: please replace below with CIO command to destroy volume.
        # destroy_result = self.connection.delete_volume(blockdevice_id)
        # END TODO

        # TODO: identify and throw UnknownVolume
        # END TODO

    def get_device_path(self, blockdevice_id):
        """
        Get device path for the CIO volume corresponding to the given
        block device.

        :param unicode blockdevice_id: CIO UUID for the volume to look up.

        :returns: A ``FilePath`` for the device.
        :raises UnknownVolume: If the supplied ``blockdevice_id`` does not
            exist.
        :raises UnattachedVolume: If the supplied ``blockdevice_id`` is
            not attached to a host.
        """
        cio_volume = self._get_cio_volume(blockdevice_id)
        volume = _blockdevicevolume_from_cio_volume(cio_volume)
        if volume.attached_to is None:
            raise UnattachedVolume(blockdevice_id)

        compute_instance_id = self.compute_instance_id()
        if volume.attached_to != compute_instance_id:
            # This is untested.  See FLOC-2453.
            raise Exception(
                "Volume is attached to {}, not to {}".format(
                    volume.attached_to, compute_instance_id
                )
            )

        return _expected_device(cio_volume.attach_data.device)

import shutil
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import TypeVar, List

from .utils import CaseInsensitiveEnum
from .external import CobaltStrikeClient, MythicClient, RemoteBuildClient


@dataclass
class Connector(ABC):
    class Meta:
        # this nested class is used to control mapping between a connector and its associated
        # client class as well as if a connector is intended to be unique
        # (meaning only one instance can exist in a manager)
        client_cls = None
        unique = False

    @abstractmethod
    def to_client(self):
        return self.Meta.client_cls(**self.__dict__)

    @property
    def is_unique(self) -> bool:
        # A unique connectors indicates there can only be one instance of it in the config
        # By default, connectors are not unique
        return self.Meta.unique


ConnectorT = TypeVar("ConnectorT", bound=Connector)


@dataclass
class CobaltStrikeConnector(Connector):
    class Meta:
        client_cls = CobaltStrikeClient
        unique = False

    password: str
    host: str
    port: str
    install_dir: str  # this is required since the client relies on the agscript utility

    def to_client(self):
        return super().to_client()


@dataclass
class MythicConnector(Connector):
    class Meta:
        client_cls = MythicClient
        unique = False

    password: str
    host: str
    port: str
    callback_url: str
    callback_port: str
    user: str

    def to_client(self):
        return super().to_client()


@dataclass
class RemoteBuildConnector(Connector):
    class Meta:
        client_cls = RemoteBuildClient
        # this is currently marked unique as there is no mechanism to support selecting one
        # remote builder versus another.
        # selecting one connector versus another is mainly done through the CLI, which
        # would not be appropriate for the remote connector. this likely would require a new
        # top-level payload key to control the connector
        #   this could also be expanded to work with the docker client as well to support
        #   mulitple docker daemons
        unique = True

    aws_instance_id: str
    aws_region: str
    aws_profile: str
    mnt_dir: str  # the path on the remote system that will be mounted into the job containers

    def to_client(self):
        return super().to_client()


class Connectors(CaseInsensitiveEnum):
    CobaltStrike = CobaltStrikeConnector
    Mythic = MythicConnector
    Remote = RemoteBuildConnector


@dataclass
class ClientWrapper:
    name: str
    client: object


class ClientManager:
    # this class is used to hold all clients for a run
    # clients are responsible for actually performing the activity versus connectors which
    # only hold the configs provided by users
    def __init__(self, clients: dict = None):
        self.__clients = clients if clients is not None else dict()

    @property
    def all_clients(self) -> List[ClientWrapper]:
        return [ClientWrapper(name=name, client=client) for (name, client) in self.__clients.items()]

    def get_client_by_name(self, client_name: str) -> ClientWrapper:
        client = self.__clients.get(client_name, None)
        if client is None:
            raise Exception(f"Client {client_name} not found")

        return ClientWrapper(name=client_name, client=client)

    def get_clients_by_type(self, client_type) -> List[ClientWrapper]:
        return [
            ClientWrapper(name=client_name, client=client)
            for (client_name, client) in self.__clients.items()
            if type(client) == client_type
        ]

    def upsert_client(self, client_name: str, client):
        # TODO: upsert by wrapper?
        self.__clients[client_name] = client

    def upsert_clients_from_manager(self, manager: "ClientManager"):
        for cw in manager.all_clients:
            self.upsert_client(client_name=cw.name, client=cw.client)


def convert_connector_dict_to_clients(connector_dict: dict) -> ClientManager:
    # this method is responsible for converting a dict of connector config info
    # into a client manager instance. the connector info should be sourced from either
    # the global or config connectors
    clients = {}
    unique_connector_types = set()
    for name, config in connector_dict.items():  # type: str, dict
        # a few connector names are blacklisted to prevent lookup issues with builtin connectors
        # e.g. you cannot name a Cobalt Strike connector "artifact" as it would prevent
        # using @artifact to access the builtin artifact functionality
        # TODO: these names should be pulled from the classes rather than provided as strings
        if name in ["docker", "files", "artifact"]:
            raise Exception(f"{name} not a valid connector name")
        try:
            connector_member = Connectors(config.get("type"))
            connector_arg_cls = connector_member.value
            connector_args = config.get("args")
        except KeyError:
            raise Exception(f"Unknown connector type {name} or missing args section")

        try:
            connector: ConnectorT = connector_arg_cls(**connector_args)

            # check for connector uniqueness constraints
            connector_type = type(connector)
            if connector.is_unique and connector_type in unique_connector_types:
                # TODO: break this uniqueness check out into a different try/catch
                raise Exception(f"Cannot have more than one connector of type: {connector_type}")
            else:
                unique_connector_types.add(connector_type)
        except Exception as e:
            raise e  # TODO
        else:
            clients[name] = connector.to_client()
    return ClientManager(clients=clients)

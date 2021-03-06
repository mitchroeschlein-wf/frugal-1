import os
import logging
import sys
import asyncio
import uuid

from nats.aio.client import Client as NatsClient
from thrift.protocol import TBinaryProtocol
from thrift.transport.TTransport import TTransportException
from frugal.context import FContext
from frugal.protocol import FProtocolFactory
from frugal.provider import FServiceProvider
from frugal.aio.transport import FNatsTransport

sys.path.append(os.path.join(os.path.dirname(__file__), "gen-py.asyncio"))
from v1.music.f_Store import Client as FStoreClient  # noqa
from v1.music.ttypes import Album  # noqa


root = logging.getLogger()
root.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)


async def main():
    # Declare the protocol stack used for serialization.
    # Protocol stacks must match between clients and servers.
    prot_factory = FProtocolFactory(TBinaryProtocol.TBinaryProtocolFactory())

    # Open a NATS connection to send requests
    nats_client = NatsClient()
    options = {
        "verbose": True,
        "servers": ["nats://127.0.0.1:4222"]
    }
    await nats_client.connect(**options)

    # Create a nats transport using the connected client
    # The transport sends data on the music-service NATS topic
    nats_transport = FNatsTransport(nats_client, "music-service")
    try:
        await nats_transport.open()
    except TTransportException as ex:
        root.error(ex)
        return

    # Using the configured transport and protocol, create a client
    # to talk to the music store service.
    store_client = FStoreClient(FServiceProvider(nats_transport, prot_factory),
                                middleware=logging_middleware)

    album = await store_client.buyAlbum(FContext(),
                                        str(uuid.uuid4()),
                                        "ACT-12345")

    root.info("Bought an album %s\n", album.tracks[0].title)

    await store_client.enterAlbumGiveaway(FContext(),
                                          "kevin@workiva.com",
                                          "Kevin")

    # Close transport and nats client
    await nats_transport.close()
    await nats_client.close()


def logging_middleware(next):
    def handler(method, args):
        root.info('==== CALLING %s ====', method.__name__)
        ret = next(method, args)
        root.info('==== CALLED  %s ====', method.__name__)
        return ret
    return handler


if __name__ == '__main__':
    io_loop = asyncio.get_event_loop()
    io_loop.run_until_complete(main())

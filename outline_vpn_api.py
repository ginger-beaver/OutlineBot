import typing
import asyncio

from aiohttp import ClientSession, TCPConnector, Fingerprint
from dataclasses import dataclass

@dataclass
class OutlineKey:
    key_id: int
    name: str
    password: str
    port: int
    method: str
    access_url: str
    used_bytes: int
    data_limit: typing.Optional[int]

class OutlineServerErrorException(Exception):
    pass

class OutlineVPN:
    def __init__(self, api_url: str, fingerprint: str):
        self.api_url = api_url

        fingerprint_generator = (f"{fingerprint[i]}{fingerprint[i + 1]}" for i in range(0, len(fingerprint), 2))
        fingerprint_to_bytes = bytes(int(i, 16) for i in fingerprint_generator)
        self.session = ClientSession(connector=TCPConnector(ssl=Fingerprint(fingerprint_to_bytes)))

    async def close(self):
        await self.session.close()

    async def get_keys(self) -> list:
        async with (
            self.session.get(f"{self.api_url}/access-keys/") as response,
            self.session.get(f"{self.api_url}/metrics/transfer") as response_metrics
        ):
            if response.ok and response_metrics.ok:
                response_json, response_metrics_json = await response.json(), await response_metrics.json()
                result = []
                for key in response_json.get("accessKeys"):
                    result.append(
                        OutlineKey(
                            key_id=key.get("id"),
                            name=key.get("name"),
                            password=key.get("password"),
                            port=key.get("port"),
                            method=key.get("method"),
                            access_url=key.get("accessUrl").replace('?outline=1', '#GingerBeaverVpn 🇳🇱'),
                            data_limit=key.get("dataLimit", {}).get("bytes"),
                            used_bytes=response_metrics_json
                            .get("bytesTransferredByUserId")
                            .get(key.get("id")),
                        )
                    )
                return result

            raise OutlineServerErrorException("Unable to get keys!")

    async def create_key(self, key_name: str = None) -> OutlineKey:
        async with self.session.post(f"{self.api_url}/access-keys/") as request:
            if request.ok:
                key = await request.json()
                outline_key = OutlineKey(
                    key_id=key.get("id"),
                    name=key.get("name"),
                    password=key.get("password"),
                    port=key.get("port"),
                    method=key.get("method"),
                    access_url=key.get("accessUrl").replace('?outline=1', '#GingerBeaverVpn 🇳🇱'),
                    used_bytes=0,
                    data_limit=None,
                )
                if key_name is None:
                    key_name = f"Ключ {outline_key.key_id}"
                if await self.rename_key(outline_key.key_id, key_name):
                    outline_key.name = key_name
                return outline_key

        raise OutlineServerErrorException("Unable to create key")

    async def delete_key(self, key_id: int) -> bool:
        async with self.session.delete(f"{self.api_url}/access-keys/{key_id}") as request:
            return request.ok

    async def rename_key(self, key_id: int, key_name: str) -> bool:
        async with self.session.put(f"{self.api_url}/access-keys/{key_id}/name/", data={"name": key_name}) as request:
            return request.ok

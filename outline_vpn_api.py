import typing

from aiohttp import ClientSession, TCPConnector, Fingerprint
from dataclasses import dataclass


@dataclass
class OutlineKey:
    key_id: int
    name: str
    access_url: str
    used_bytes: int
    data_limit: typing.Optional[int]

    def get_stats(self) -> str:
        used_bytes = round(self.used_bytes * 1e-9, 2)
        if self.data_limit is None:
            return f"({used_bytes} / None ГБ)"

        return f"({used_bytes} / {round(self.data_limit * 1e-9, 2)} ГБ)"

    def __str__(self):
        return f"ID: {self.key_id}, Name: {self.name}"

    def get_formatted_url(self):
        return f"<code>{self.access_url.replace('?outline=1', '#GingerBeaverVpn 🇳🇱')}</code>"


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

    async def get_keys(self) -> list[OutlineKey]:
        async with (
            self.session.get(f"{self.api_url}/access-keys/") as response,
            self.session.get(f"{self.api_url}/metrics/transfer") as response_metrics
        ):
            if response.ok and response_metrics.ok:
                response_json, response_metrics_json = await response.json(), await response_metrics.json()
                result = []
                default_limit = await self.get_default_data_limit()
                key_limit = 0
                for key in response_json.get("accessKeys"):
                    data_limit = key.get("dataLimit", {}).get("bytes")
                    key_limit = data_limit if (data_limit or data_limit == 0) else default_limit
                    result.append(
                        OutlineKey(
                            key_id=key.get("id"),
                            name=key.get("name"),
                            access_url=key.get("accessUrl"),
                            data_limit=key_limit,
                            used_bytes=response_metrics_json
                                       .get("bytesTransferredByUserId")
                                       .get(key.get("id")) or 0,
                        )
                    )
                return result

            raise OutlineServerErrorException("Unable to get keys!")

    async def create_key(self, key_name: str = None) -> OutlineKey:
        async with self.session.post(f"{self.api_url}/access-keys/") as response:
            if response.ok:
                key = await response.json()
                limit = await self.get_default_data_limit()
                outline_key = OutlineKey(
                    key_id=key.get("id"),
                    name=key.get("name"),
                    access_url=key.get("accessUrl"),
                    used_bytes=0,
                    data_limit=limit,
                )
                if key_name is None:
                    key_name = f"Ключ {outline_key.key_id}"
                if await self.rename_key(outline_key.key_id, key_name):
                    outline_key.name = key_name
                return outline_key

        raise OutlineServerErrorException("Unable to create key")

    async def delete_key(self, key_id: int) -> bool:
        async with self.session.delete(f"{self.api_url}/access-keys/{key_id}") as response:
            return response.ok

    async def rename_key(self, key_id: int, key_name: str) -> bool:
        data = {"name": key_name}
        async with self.session.put(f"{self.api_url}/access-keys/{key_id}/name/", data=data) as response:
            return response.ok

    async def get_key(self, key_id: int) -> OutlineKey | None:
        for key in await self.get_keys():
            if int(key.key_id) == key_id:
                return key

        return None

    # async def set_data_limit(self, key_id: int, bytes_limit: int) -> bool:
    #     data = {"limit": bytes_limit}
    #     async with self.session.put(f"{self.api_url}/access-keys/{key_id}/data-limit", data=data) as response:
    #         return response.ok
    #
    # async def delete_data_limit(self, key_id: int) -> bool:
    #     async with self.session.delete(f"{self.api_url}/access-keys/{key_id}/data-limit") as response:
    #         return response.ok
    #
    # async def disable_user(self, key_id: int) -> bool:
    #     return await self.set_data_limit(key_id, 0)
    #
    # async def enable_user(self, key_id: int) -> bool:
    #     return await self.delete_data_limit(key_id)

    async def get_default_data_limit(self):
        async with self.session.get(f"{self.api_url}/server") as response:
            try:
                server_info = await response.json()
                return server_info.get("accessKeyDataLimit").get("bytes")
            except AttributeError:
                return None

    # async def set_default_data_limit(self, bytes_limit: int):
    #     data = '{\"limit\": 10000}'
    #     async with self.session.put(f"{self.api_url}/server/access-key-data-limit", data=data) as response:
    #         print(response.status)
    #         return response.ok
    #
    # async def delete_default_data_limit(self):
    #     async with self.session.delete(f"{self.api_url}/server/access-key-data-limit") as response:
    #         return response.ok

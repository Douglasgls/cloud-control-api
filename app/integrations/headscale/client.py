from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Any
import urllib.parse
import httpx

from app.integrations.headscale.dto import (
    HeadscaleUserDTO,
    HeadscaleUserListDTO,
    HeadscalePreAuthKeyDTO,
    HeadscalePreAuthKeyListDTO,
    HeadscaleNodeDTO,
    HeadscaleNodeListDTO,
)
from app.integrations.headscale.exceptions import (
    HeadscaleError,
    HeadscaleConnectionError,
    HeadscaleAuthenticationError,
    HeadscaleRequestError,
    HeadscaleNotFoundError,
)


class IHeadscaleClient(ABC):
    @abstractmethod
    def create_user(self, name: str) -> HeadscaleUserDTO:
        pass

    @abstractmethod
    def list_users(self) -> HeadscaleUserListDTO:
        pass

    @abstractmethod
    def get_user(self, name: str) -> HeadscaleUserDTO:
        pass

    @abstractmethod
    def delete_user(self, name: str) -> None:
        pass

    @abstractmethod
    def rename_user(self, old_name: str, new_name: str) -> HeadscaleUserDTO:
        pass

    @abstractmethod
    def create_preauth_key(
        self,
        user: str,
        reusable: bool = False,
        ephemeral: bool = False,
        expiration: Optional[datetime] = None,
    ) -> HeadscalePreAuthKeyDTO:
        pass

    @abstractmethod
    def expire_preauth_key(self, user: str, key: str) -> None:
        pass

    @abstractmethod
    def list_preauth_keys(self, user: str) -> HeadscalePreAuthKeyListDTO:
        pass

    @abstractmethod
    def list_nodes(self, user: Optional[str] = None) -> HeadscaleNodeListDTO:
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> HeadscaleNodeDTO:
        pass

    @abstractmethod
    def delete_node(self, node_id: str) -> None:
        pass

    @abstractmethod
    def rename_node(self, node_id: str, new_name: str) -> HeadscaleNodeDTO:
        pass

    @abstractmethod
    def move_node(self, node_id: str, user: str) -> HeadscaleNodeDTO:
        pass

    @abstractmethod
    def health_check(self) -> bool:
        pass


class RestHeadscaleClient(IHeadscaleClient):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 10.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        base = (base_url or "").strip().rstrip("/")
        if base and not (base.startswith("http://") or base.startswith("https://")):
            base = f"http://{base}"
        self.base_url = base
        self.api_key = api_key
        self.timeout = timeout

        if client is not None:
            self.client = client
        else:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            self.client = httpx.Client(headers=headers, timeout=self.timeout)

    def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Any] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        try:
            response = self.client.request(method, url, json=json_data, params=params)

            if response.status_code in (401, 403):
                raise HeadscaleAuthenticationError("Authentication with Headscale failed.")

            if response.status_code == 404:
                raise HeadscaleNotFoundError(
                    f"Resource not found at {path}",
                    status_code=404,
                    response_body=response.text,
                )

            if response.status_code >= 400:
                raise HeadscaleRequestError(
                    f"Headscale request failed with status {response.status_code}",
                    status_code=response.status_code,
                    response_body=response.text,
                )

            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HeadscaleNotFoundError("Resource not found", status_code=404, response_body=e.response.text)
            raise HeadscaleRequestError(str(e), status_code=e.response.status_code, response_body=e.response.text)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout) as e:
            raise HeadscaleConnectionError(f"Failed to connect to Headscale: {str(e)}")
        except HeadscaleError:
            raise
        except Exception as e:
            raise HeadscaleError(f"Unexpected error: {str(e)}")

    def create_user(self, name: str) -> HeadscaleUserDTO:
        res = self._request("POST", "/api/v1/user", json_data={"name": name})
        data = res.json()
        user_data = data.get("user", data)
        return HeadscaleUserDTO.model_validate(user_data)

    def list_users(self) -> HeadscaleUserListDTO:
        res = self._request("GET", "/api/v1/user")
        return HeadscaleUserListDTO.model_validate(res.json())

    def get_user(self, name: str) -> HeadscaleUserDTO:
        # Resolve user by name since REST API get user endpoint has changed or uses listing/filtering.
        # Find user from the user list.
        users_list = self.list_users()
        for u in users_list.users:
            if u.name == name:
                return u
        raise HeadscaleNotFoundError(f"User '{name}' not found.", status_code=404)

    def delete_user(self, name: str) -> None:
        self._request("DELETE", f"/api/v1/user/{name}")

    def rename_user(self, old_name: str, new_name: str) -> HeadscaleUserDTO:
        res = self._request("POST", f"/api/v1/user/{old_name}/rename/{new_name}")
        data = res.json()
        user_data = data.get("user", data)
        return HeadscaleUserDTO.model_validate(user_data)

    def create_preauth_key(
        self,
        user: str,
        reusable: bool = False,
        ephemeral: bool = False,
        expiration: Optional[datetime] = None,
    ) -> HeadscalePreAuthKeyDTO:
        body: dict[str, Any] = {
            "user": user,
            "reusable": reusable,
            "ephemeral": ephemeral,
        }
        if expiration is not None:
            body["expiration"] = expiration.isoformat().replace("+00:00", "Z")

        res = self._request("POST", "/api/v1/preauthkey", json_data=body)
        data = res.json()
        key_data = data.get("preAuthKey") or data.get("preauthKey") or data
        return HeadscalePreAuthKeyDTO.model_validate(key_data)

    def expire_preauth_key(self, user: str, key: str) -> None:
        body = {
            "user": user,
            "key": key,
        }
        self._request("POST", "/api/v1/preauthkey/expire", json_data=body)

    def list_preauth_keys(self, user: str) -> HeadscalePreAuthKeyListDTO:
        res = self._request("GET", "/api/v1/preauthkey", params={"user": user})
        data = res.json()
        if "preAuthKeys" in data:
            data["preauthKeys"] = data.pop("preAuthKeys")
        return HeadscalePreAuthKeyListDTO.model_validate(data)

    def list_nodes(self, user: Optional[str] = None) -> HeadscaleNodeListDTO:
        params = {}
        if user:
            params["user"] = user
        res = self._request("GET", "/api/v1/node", params=params)
        return HeadscaleNodeListDTO.model_validate(res.json())

    def get_node(self, node_id: str) -> HeadscaleNodeDTO:
        res = self._request("GET", f"/api/v1/node/{node_id}")
        data = res.json()
        node_data = data.get("node", data)
        return HeadscaleNodeDTO.model_validate(node_data)

    def delete_node(self, node_id: str) -> None:
        self._request("DELETE", f"/api/v1/node/{node_id}")

    def rename_node(self, node_id: str, new_name: str) -> HeadscaleNodeDTO:
        encoded_name = urllib.parse.quote(new_name)
        res = self._request("POST", f"/api/v1/node/{node_id}/rename/{encoded_name}")
        data = res.json()
        node_data = data.get("node", data)
        return HeadscaleNodeDTO.model_validate(node_data)

    def move_node(self, node_id: str, user: str) -> HeadscaleNodeDTO:
        res = self._request("POST", f"/api/v1/node/{node_id}/user", params={"user": user}, json_data={"user": user})
        data = res.json()
        node_data = data.get("node", data)
        return HeadscaleNodeDTO.model_validate(node_data)

    def health_check(self) -> bool:
        try:
            # Check ping / list_users or hit a standard endpoint.
            # Using GET /api/v1/user since it exists on all versions of Headscale with v1 API.
            self.list_users()
            return True
        except Exception:
            return False

import asyncio
import httpx

async def test_auth():
    async with httpx.AsyncClient(base_url="http://localhost:8000/api/v1") as client:
        # 1. Register organization
        reg_payload = {
            "name": "Test Auth Org",
            "email": "auth_test_org@example.com",
            "password": "SecretPassword123!"
        }
        res = await client.post("/auth/register", json=reg_payload)
        print("Register status:", res.status_code)
        if res.status_code == 400: # Already registered
            print("Org already registered, proceeding to login...")
        
        # 2. Login
        login_res = await client.post("/auth/login", data={"username": reg_payload["email"], "password": reg_payload["password"]})
        print("Login status:", login_res.status_code)
        token_data = login_res.json()
        token = token_data.get("access_token")
        print("Access Token acquired:", token[:20] if token else None)

        # 3. Fetch /auth/me
        me_res = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        print("/auth/me status:", me_res.status_code)
        print("/auth/me response:", me_res.json())

if __name__ == "__main__":
    asyncio.run(test_auth())

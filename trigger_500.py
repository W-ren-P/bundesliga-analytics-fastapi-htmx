import asyncio
from main import app
from httpx import AsyncClient

async def test_home():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        try:
            response = await ac.get("/")
            print(f"Status: {response.status_code}")
            if response.status_code == 500:
                print("500 Error detected!")
                # Starlette/FastAPI usually don't return the traceback in the body unless configured
                # But running it here should show the traceback in our terminal if it's a code error.
            else:
                print(f"Response: {response.text[:500]}...")
        except Exception as e:
            print(f"Caught Exception: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_home())

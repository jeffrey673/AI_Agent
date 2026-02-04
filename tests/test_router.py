"""Tests for Query Router and API endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestAPIEndpoints:
    """Tests for FastAPI endpoint availability."""

    def setup_method(self):
        from app.main import app
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_list_models(self):
        response = self.client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) >= 1

        model_ids = [m["id"] for m in data["data"]]
        assert "skin1004-ai" in model_ids

    def test_chat_completions_missing_messages(self):
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "skin1004-ai",
                "messages": [],
            },
        )
        # Should return 400 or handle gracefully
        assert response.status_code in [400, 422]

    def test_chat_completions_no_user_message(self):
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "skin1004-ai",
                "messages": [
                    {"role": "system", "content": "You are helpful."}
                ],
            },
        )
        assert response.status_code == 400

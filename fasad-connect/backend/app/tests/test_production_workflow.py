from __future__ import annotations


def _create_order_from_lead(client, auth_headers):
    lead_response = client.post(
        "/api/v1/leads/intake",
        json={
            "source_channel": "website_form",
            "text": "Name: Production Client, phone +79991112233, email production@example.com, wardrobe 1200x2400x600",
            "raw_payload": {"form_id": "wf-production"},
        },
    )
    lead_id = lead_response.json()["data"]["id"]
    order_response = client.post(
        f"/api/v1/leads/{lead_id}/create-order", json={}, headers=auth_headers
    )
    return order_response.json()["data"]["id"]


def _prepare_order_parts(client, auth_headers, order_id: str) -> list[dict]:
    template_id = client.get("/api/v1/templates?page=1&size=10", headers=auth_headers).json()[
        "data"
    ][0]["id"]
    client.post(
        f"/api/v1/orders/{order_id}/items",
        json={
            "template_id": template_id,
            "item_type": "wardrobe_basic",
            "name": "Wardrobe production",
            "width": 1200,
            "height": 2400,
            "depth": 600,
            "quantity": 1,
        },
        headers=auth_headers,
    )
    client.post(f"/api/v1/orders/{order_id}/generate-parts", headers=auth_headers)
    return client.get(f"/api/v1/orders/{order_id}/parts", headers=auth_headers).json()["data"]


def test_bootstrap_workflow_creates_first_stage(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)

    response = client.post(
        f"/api/v1/orders/{order_id}/workflow/bootstrap",
        json={},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "pending"
    assert data["workflow_stage"]["code"] == "cutting"

    list_response = client.get(f"/api/v1/orders/{order_id}/stages", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 1


def test_part_report_is_linked_to_part_and_worker(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)
    parts = _prepare_order_parts(client, auth_headers, order_id)
    bootstrap_response = client.post(
        f"/api/v1/orders/{order_id}/workflow/bootstrap",
        json={},
        headers=auth_headers,
    )
    stage_id = bootstrap_response.json()["data"]["id"]

    report_response = client.post(
        f"/api/v1/production/stages/{stage_id}/part-reports",
        headers=auth_headers,
        data={
            "part_id": parts[0]["id"],
            "quantity_done": "1",
            "quantity_defect": "0",
            "comment": "Cut part completed",
        },
        files={"file": ("part.jpg", b"fake-image-content", "image/jpeg")},
    )

    assert report_response.status_code == 200
    report = report_response.json()["data"]
    assert report["part_id"] == parts[0]["id"]
    assert report["worker"]["login"] == "admin"
    assert report["photo_file_name"] == "part.jpg"

    stage_response = client.get(f"/api/v1/production/stages/{stage_id}", headers=auth_headers)
    assert stage_response.status_code == 200
    assert stage_response.json()["data"]["status"] == "in_progress"


def test_complete_stage_opens_next_stage_after_all_part_reports(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)
    _prepare_order_parts(client, auth_headers, order_id)
    bootstrap_response = client.post(
        f"/api/v1/orders/{order_id}/workflow/bootstrap",
        json={},
        headers=auth_headers,
    )
    stage_id = bootstrap_response.json()["data"]["id"]

    progress_response = client.get(
        f"/api/v1/production/stages/{stage_id}/part-progress",
        headers=auth_headers,
    )
    progress = progress_response.json()["data"]

    incomplete_complete = client.post(
        f"/api/v1/production/stages/{stage_id}/complete",
        json={"comment": "Try to close early"},
        headers=auth_headers,
    )
    assert incomplete_complete.status_code == 400

    for index, item in enumerate(progress):
        files = (
            {"file": (f"part-{index}.jpg", b"fake-image-content", "image/jpeg")}
            if index == 0
            else None
        )
        response = client.post(
            f"/api/v1/production/stages/{stage_id}/part-reports",
            headers=auth_headers,
            data={
                "part_id": item["part"]["id"],
                "quantity_done": str(item["required_quantity"]),
                "quantity_defect": "0",
                "comment": f"Reported {item['part']['part_code']}",
            },
            files=files,
        )
        assert response.status_code == 200

    complete_response = client.post(
        f"/api/v1/production/stages/{stage_id}/complete",
        json={"comment": "Cutting completed"},
        headers=auth_headers,
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["data"]["status"] == "done"

    stages_response = client.get(f"/api/v1/orders/{order_id}/stages", headers=auth_headers)
    stages = stages_response.json()["data"]
    assert len(stages) == 2
    assert stages[0]["workflow_stage"]["code"] == "cutting"
    assert stages[1]["workflow_stage"]["code"] == "assembly"
    assert stages[1]["status"] == "pending"


def test_worker_card_and_dashboard_production_stats(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)
    parts = _prepare_order_parts(client, auth_headers, order_id)
    stage_id = client.post(
        f"/api/v1/orders/{order_id}/workflow/bootstrap",
        json={},
        headers=auth_headers,
    ).json()["data"]["id"]

    client.post(
        f"/api/v1/production/stages/{stage_id}/part-reports",
        headers=auth_headers,
        data={
            "part_id": parts[0]["id"],
            "quantity_done": "1",
            "quantity_defect": "0",
            "comment": "Worker report",
        },
        files={"file": ("worker.jpg", b"fake-image-content", "image/jpeg")},
    )

    worker_response = client.get("/api/v1/workers/me", headers=auth_headers)
    assert worker_response.status_code == 200
    worker = worker_response.json()["data"]
    assert worker["completed_reports_count"] >= 1
    assert worker["done_quantity"] >= 1

    dashboard_response = client.get("/api/v1/dashboard/summary", headers=auth_headers)
    assert dashboard_response.status_code == 200
    production = dashboard_response.json()["data"]["production"]
    assert production["active_stages"] >= 1
    assert production["completed_reports"] >= 1
    assert production["done_quantity"] >= 1


def test_part_report_rejects_overreported_quantity(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)
    parts = _prepare_order_parts(client, auth_headers, order_id)
    stage_id = client.post(
        f"/api/v1/orders/{order_id}/workflow/bootstrap",
        json={},
        headers=auth_headers,
    ).json()["data"]["id"]

    first_response = client.post(
        f"/api/v1/production/stages/{stage_id}/part-reports",
        headers=auth_headers,
        data={
            "part_id": parts[0]["id"],
            "quantity_done": str(parts[0]["quantity"]),
            "quantity_defect": "0",
            "comment": "Reported full quantity",
        },
        files={"file": ("full.jpg", b"fake-image-content", "image/jpeg")},
    )
    assert first_response.status_code == 200

    overreported_response = client.post(
        f"/api/v1/production/stages/{stage_id}/part-reports",
        headers=auth_headers,
        data={
            "part_id": parts[0]["id"],
            "quantity_done": "1",
            "quantity_defect": "0",
            "comment": "Overreported quantity",
        },
    )
    assert overreported_response.status_code == 400
    assert "exceeds required quantity" in overreported_response.json()["error"]["message"]


def test_photo_required_stage_cannot_complete_without_photo(client, auth_headers):
    order_id = _create_order_from_lead(client, auth_headers)
    _prepare_order_parts(client, auth_headers, order_id)
    stage_id = client.post(
        f"/api/v1/orders/{order_id}/workflow/bootstrap",
        json={},
        headers=auth_headers,
    ).json()["data"]["id"]

    progress = client.get(
        f"/api/v1/production/stages/{stage_id}/part-progress",
        headers=auth_headers,
    ).json()["data"]

    for item in progress:
        response = client.post(
            f"/api/v1/production/stages/{stage_id}/part-reports",
            headers=auth_headers,
            data={
                "part_id": item["part"]["id"],
                "quantity_done": str(item["required_quantity"]),
                "quantity_defect": "0",
                "comment": f"Reported {item['part']['part_code']}",
            },
        )
        assert response.status_code == 200

    missing_photo_response = client.post(
        f"/api/v1/production/stages/{stage_id}/complete",
        json={"comment": "Try to complete without photo"},
        headers=auth_headers,
    )
    assert missing_photo_response.status_code == 400
    assert "Photo evidence is required" in missing_photo_response.json()["error"]["message"]

    evidence_response = client.post(
        f"/api/v1/production/stages/{stage_id}/evidence",
        headers=auth_headers,
        data={"evidence_type": "photo", "comment": "Stage completion photo"},
        files={"file": ("completion.jpg", b"fake-image-content", "image/jpeg")},
    )
    assert evidence_response.status_code == 200

    complete_response = client.post(
        f"/api/v1/production/stages/{stage_id}/complete",
        json={"comment": "Photo uploaded, complete now"},
        headers=auth_headers,
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["data"]["status"] == "done"

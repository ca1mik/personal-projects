from __future__ import annotations


def test_film_cutting_estimate_returns_layout(client, auth_headers):
    response = client.post(
        "/api/v1/templates/film-cutting/estimate",
        headers=auth_headers,
        json={
            "roll_width_mm": 1400,
            "trim_margin_mm": 70,
            "lines": [
                {
                    "catalog_item_code": "kitchen_facade_716_396",
                    "name": "Фасад кухни 716x396",
                    "length_mm": 716,
                    "width_mm": 396,
                    "quantity": 2,
                    "depth_mm": 20,
                    "milling_code": "frame_light",
                    "color_code": "white_gloss",
                },
                {
                    "name": "Фасад шкафа",
                    "length_mm": 2200,
                    "width_mm": 500,
                    "quantity": 1,
                    "depth_mm": 18,
                    "milling_code": "flat",
                    "color_code": "graphite_matt",
                },
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_details"] == 3
    assert float(data["total_net_area_sqm"]) > 0
    assert float(data["estimated_roll_area_sqm"]) >= float(data["total_blank_area_sqm"])
    assert len(data["color_plans"]) == 2
    assert data["color_plans"][0]["layout_rows"]


def test_film_cutting_lead_creates_crm_lead(client, auth_headers):
    response = client.post(
        "/api/v1/templates/film-cutting/lead",
        headers=auth_headers,
        json={
            "roll_width_mm": 1400,
            "trim_margin_mm": 70,
            "client_name": "Мария Смирнова",
            "phone": "+79990000000",
            "comment": "Нужен расчет по двум цветам",
            "lines": [
                {
                    "catalog_item_code": "bathroom_facade_596_296",
                    "length_mm": 596,
                    "width_mm": 296,
                    "quantity": 4,
                    "depth_mm": 16,
                    "milling_code": "wave",
                    "color_code": "oak_natural",
                }
            ],
        },
    )

    assert response.status_code == 200
    lead = response.json()["data"]
    assert lead["source_channel"] == "manager_film_cutting"
    assert "film_cutting_estimate" in lead["parsed_payload_json"]["raw_payload"]
    assert lead["client"]["phone"] == "+79990000000"

# Room Viewer & Test Case Tool

## Tổng quan

`room_viewer.html` là tool trực quan hoá mặt bằng phòng từ 21 căn hộ mẫu, kèm editor để soạn thảo test case cho pipeline xếp đồ.

---

## Chạy tool

### 1. Mở Room Viewer (không cần backend)

```bash
cd /Users/Yuki/DesignAI
python3 -m http.server 7788
```

Mở trình duyệt: **http://localhost:7788/room_viewer.html**

---

### 2. Chạy backend API (để dùng nút Run)

Backend chạy qua Docker Compose:

```bash
cd /Users/Yuki/DesignAI/backend
docker compose up
```

API sẽ lắng nghe tại **http://localhost:8000**.

Hoặc chạy thẳng không dùng Docker (cần `uv`):

```bash
cd /Users/Yuki/DesignAI/backend
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Sử dụng Room Viewer

### Lọc phòng
- **Dropdown chung cư** — lọc theo toà nhà
- **Sinh hoạt / Ngủ** — lọc theo loại phòng
- Số liệu tổng hợp hiển thị ở sidebar trái

### Panel test case

Mỗi card phòng khách hoặc phòng ngủ có link **🧪 test case** ở dưới cùng. Click để mở panel:

| Thành phần | Chức năng |
|---|---|
| Textarea | Mô tả yêu cầu người dùng — soạn thảo tự do |
| ✅ đã lưu | Tự động hiện sau khi gõ, xác nhận đã lưu |
| ↩ reset | Xoá bản chỉnh sửa, về lại description gốc |
| 📋 Copy payload | Copy JSON payload sẵn sàng dùng với curl/Postman |
| ▶ Run | Gửi request tới backend, hiển thị kết quả inline |

> **Lưu ý:** chỉnh sửa được lưu tự động vào `localStorage` sau ~600ms. Reload trang vẫn giữ nguyên.
> Card đã chỉnh sửa sẽ hiện thêm ✏️ trên link.

---

## Format mô tả (description)

```
<Tên phòng> đầy đủ đồ có <danh sách đồ vật với kích thước>.
<Vị trí đặt đồ>. Chi phí tối đa X triệu.
```

Từ khoá trigger chế độ generous (nhồi nhiều đồ nhất): `đầy đủ đồ`, `càng nhiều`, `nhiều đồ`.

Ví dụ phòng khách + bếp:
```
Phòng khách + bếp + ăn đầy đủ đồ có sofa chữ L 2.6m x 1.6m màu xanh navy;
kệ TV 1.6m x 0.4m; bàn trà 1.1m x 0.6m; 1 ghế armchair 0.85m x 0.85m;
thảm 2.0m x 3.0m; 1 bàn ăn 1.6m x 0.9m cùng 6 ghế ăn; tủ bếp rustic đặt sát tường bếp.
Sofa đặt sát tường dài hướng về TV; bàn ăn đặt gần khu bếp; tủ bếp đặt sát tường.
Chi phí tối đa 65 triệu.
```

---

## Chạy integration tests

```bash
cd /Users/Yuki/DesignAI/backend

# Test phòng khách/sinh hoạt (8 case)
uv run python -m pytest test_generous_living_rooms.py -v

# Test phòng ngủ (17 case)
uv run python -m pytest test_generous_bedrooms.py -v
```

> Backend phải đang chạy trước khi chạy test. Test sẽ bị skip tự động nếu server không có mặt.

---

## Copy payload và test thủ công

Bấm **📋 Copy payload** để lấy JSON, rồi gửi bằng curl:

```bash
curl -s -X POST http://localhost:8000/pipeline/normalize-run \
  -H "Content-Type: application/json" \
  -d '<paste payload>' | jq .id
```

Poll trạng thái:

```bash
JOB_ID=<id từ bước trên>
curl -s http://localhost:8000/pipeline/normalize-run/$JOB_ID/status | jq .status
curl -s http://localhost:8000/pipeline/normalize-run/$JOB_ID/result | jq '[.layouts[].objects[].object_type] | unique'
```

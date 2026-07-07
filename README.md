# VachaSpeech Thai TTS

ระบบสังเคราะห์เสียงภาษาไทยแบบ Voice Cloning รันบน Docker (รองรับ GPU)

ใช้โมเดล [VachaSpeech](https://github.com/VYNCX/VachaSpeech) โดย [VIZINTZOR](https://huggingface.co/VIZINTZOR/VachaSpeech)

## เริ่มต้น (CPU)

```powershell
docker compose up -d
```

รอประมาณ 30-60 วินาทีให้โมเดลโหลด แล้วเปิด `http://localhost:7860`

หรือเปิด `index.html` ใน browser เพื่อใช้งานหน้าเว็บ

## GPU Setup (Windows + Docker Desktop + WSL 2)

รองรับ NVIDIA GPU (ทดสอบกับ RTX 4060)

### ความต้องการ

- Docker Desktop ที่ใช้ WSL 2 backend
- NVIDIA Driver บน Windows (ที่รองรับ WSL 2)
- WSL 2 distro เช่น Ubuntu

### ทดสอบว่า Docker เห็น GPU

```powershell
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

ถ้าเห็น GPU แสดงว่าพร้อมใช้งาน

### Build และรันด้วย GPU

```powershell
docker compose build
docker compose up
```

Container จะใช้ GPU โดยอัตโนมัติ (CUDA 12.1) ช่วยให้ TTS เร็วขึ้นมากเมื่อเทียบกับ CPU

## วิธีใช้ (หน้าเว็บ)

1. เปิด `index.html`
2. พิมพ์ข้อความภาษาไทย
3. เลือก **เสียงอ้างอิง** (ref audio) ที่ต้องการ
4. กด **สร้างเสียง**
5. ฟังผลลัพธ์จาก player

### อัดเสียงอ้างอิง

1. กดปุ่ม **อัดเสียง** (แดง) ข้าง dropdown
2. อนุญาตไมโครโฟน
3. กด **หยุด** เมื่ออัดเสร็จ
4. ไฟล์จะถูกบันทึกที่ `/ref_audio/` และเลือกให้อัตโนมัติ

### พารามิเตอร์

| พารามิเตอร์ | ค่าเริ่มต้น | คำอธิบาย |
|---|---|---|
| Temperature | 0.8 | ความสุ่มของเสียง (ต่ำ=นิ่ง, สูง=หลากหลาย) |
| Top-P | 0.95 | ความหลากหลายของคำ |
| Top-K | 40 | เลือกจาก K คำที่มีโอกาสสูงสุด |
| Repetition Penalty | 1.1 | ลดการซ้ำคำ |
| Speed | 1.0 | ความเร็วในการพูด (0.5–2.0x) |
| Token Multiplier | 5 | จำนวน token สูงสุด = ตัวคูณ x ความยาวข้อความ (เพิ่มถ้าพูดไม่จบ) |

### ปุ่มรีเซ็ตค่าเริ่มต้น

คืนค่าพารามิเตอร์ทั้งหมดกลับเป็นค่าเริ่มต้น

## API

### POST /tts

```powershell
Invoke-RestMethod -Uri http://localhost:7860/tts -Method Post `
  -Body '{"text":"สวัสดีครับ","gender":"female"}' `
  -ContentType "application/json" -OutFile output.wav
```

ใช้เสียงอ้างอิง (voice cloning) ด้วยไฟล์ `default_male.wav`:

```powershell
Invoke-RestMethod -Uri http://localhost:7860/tts -Method Post `
  -Body '{"text":"สวัสดีครับ","gender":"male","ref_audio":"/ref_audio/default_male.wav"}' `
  -ContentType "application/json" -OutFile output.wav
```

ปรับความเร็วด้วยพารามิเตอร์ `speed` (ค่า 0.5–2.0, default 1.0):

```powershell
# พูดเร็ว 1.5 เท่า
Invoke-RestMethod -Uri http://localhost:7860/tts -Method Post `
  -Body '{"text":"สวัสดีครับ","gender":"female","speed":1.5}' `
  -ContentType "application/json" -OutFile output.wav

# พูดช้าลง 0.75 เท่า
Invoke-RestMethod -Uri http://localhost:7860/tts -Method Post `
  -Body '{"text":"สวัสดีครับ","gender":"male","ref_audio":"/ref_audio/default_male.wav","speed":0.75}' `
  -ContentType "application/json" -OutFile output.wav
```

เรียก API ด้วย curl:

```bash
curl -X POST http://localhost:7860/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"สวัสดีครับ","gender":"female","speed":1.5}' \
  -o output.wav
```

ครบทุกพารามิเตอร์:

```bash
curl -X POST http://localhost:7860/tts \
  -H "Content-Type: application/json" \
  -d '{
    "text":"สวัสดีครับ สบายดีไหม",
    "gender":"female",
    "ref_audio":"/ref_audio/default_female.wav",
    "temperature":0.8,
    "top_p":0.95,
    "top_k":40,
    "repetition_penalty":1.1,
    "speed":1.2,
    "max_length_multiplier":5
  }' \
  -o output.wav
```

### GET /ref-audio-list

```powershell
Invoke-RestMethod -Uri http://localhost:7860/ref-audio-list
```

### POST /upload-ref-audio

```powershell
Invoke-RestMethod -Uri http://localhost:7860/upload-ref-audio -Method Post `
  -Form @{file=((Get-Item "myvoice.wav"))}
```

## คำสั่ง Docker

```powershell
# เริ่ม
docker compose up -d

# หยุด
docker compose down

# restart
docker compose restart

# ดู logs
docker compose logs -f
```

## การตั้งค่าที่บันทึกอัตโนมัติ

ค่า parameters ทั้งหมด (ยกเว้นข้อความ) จะถูกบันทึกใน localStorage ของ browser เมื่อมีการเปลี่ยนแปลง และโหลดกลับมาเมื่อเปิดหน้าเว็บใหม่

## Resource Limits

Container จำกัดที่ CPU 1 core, RAM 3GB

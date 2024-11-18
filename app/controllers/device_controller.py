from flask import Blueprint, jsonify, request
from ..utils.response_util import ResponseUtil
from firebase_admin import initialize_app, storage, db, firestore
from firebase_admin.firestore import SERVER_TIMESTAMP
import uuid
import time
import random
import string

device_bp = Blueprint('device', __name__)
client = firestore.client()

@device_bp.route('/device/create_device', methods=['POST'])
def create_device():
    data = request.json
    name = data.get('name')

    if not name:
        return ResponseUtil.error("Device name parameter is required", data=None, status_code=400)
    
    device_id = int(time.time())

    token = ''.join(random.choices(string.ascii_letters + string.digits, k=20))

    device = {
        "createdAt": SERVER_TIMESTAMP,
        "updatedAt": SERVER_TIMESTAMP,
        "name": name,
        "schedules": {},
        "token": token
    }

    try:
        client.collection('devices').document(str(device_id)).set(device)

        device_rtdb = {
            "lightIntensity": 0,
            "waterVol": 0,
            "watering": False,
        }

        rtdb_ref = db.reference(f'{device_id}')
        rtdb_ref.set(device_rtdb)

        return ResponseUtil.success("Device created successfully", data=token)

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)
    
@device_bp.route('/device/update_device/', methods=['POST'])
def update_device_name():
    data = request.json
    device_id = data.get('device_id')
    name = data.get('name')

    if not name:
        return ResponseUtil.error("Device name parameter is required", data=None, status_code=400)

    try:
        # Update nama device di Firestore
        device_ref = client.collection('devices').document(device_id)
        device_doc = device_ref.get()

        if device_doc.exists:
            device_ref.update({
                "name": name,
                "updatedAt": SERVER_TIMESTAMP
            })
        else:
            return ResponseUtil.error("Device not found in Firestore", status_code=404)

        return ResponseUtil.success("Device name updated successfully")

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/delete_device/<device_id>', methods=['DELETE'])
def delete_device(device_id):
    try:
        device_ref = client.collection('devices').document(device_id)
        if device_ref.get().exists:
            device_ref.delete()
        else:
            return ResponseUtil.error("Device not found in Firestore", status_code=404)

        rtdb_ref = db.reference(f'{device_id}')
        rtdb_ref.delete()

        return ResponseUtil.success("Device deleted successfully")

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/update_light_intensity', methods=['POST'])
def update_light_intensity():
    data = request.json
    token = data.get('token')
    new_light_intensity = data.get('lightIntensity')

    if not token:
        return ResponseUtil.error("Token parameter is required", data=None, status_code=400)

    if new_light_intensity is None:
        return ResponseUtil.error("lightIntensity parameter is required", data=None, status_code=400)

    try:
        # Cari device berdasarkan token
        device_ref = client.collection('devices').where('token', '==', token).limit(1).get()

        if not device_ref:
            return ResponseUtil.error("Device not found with the provided token", data=None, status_code=404)

        # Ambil device_id dari data device yang ditemukan
        device_data = device_ref[0].to_dict()
        device_id = device_ref[0].id

        # Perbarui nilai lightIntensity di Realtime Database
        rtdb_ref = db.reference(f'{device_id}/lightIntensity')
        rtdb_ref.set(new_light_intensity)

        return ResponseUtil.success("lightIntensity updated successfully", data=new_light_intensity)

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/update_water_vol', methods=['POST'])
def update_water_vol():
    data = request.json
    token = data.get('token')
    new_water_vol = data.get('waterVol')

    if not token:
        return ResponseUtil.error("Token parameter is required", data=None, status_code=400)

    if new_water_vol is None:
        return ResponseUtil.error("waterVol parameter is required", data=None, status_code=400)

    try:
        # Cari device berdasarkan token
        device_ref = client.collection('devices').where('token', '==', token).limit(1).get()

        if not device_ref:
            return ResponseUtil.error("Device not found with the provided token", data=None, status_code=404)

        # Ambil device_id dari data device yang ditemukan
        device_data = device_ref[0].to_dict()
        device_id = device_ref[0].id

        # Perbarui nilai waterVol di Realtime Database
        rtdb_ref = db.reference(f'{device_id}/waterVol')
        rtdb_ref.set(new_water_vol)

        return ResponseUtil.success("waterVol updated successfully", data=new_water_vol)

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)


@device_bp.route('/device/my', methods=['GET'])
def my_devices():
    data = request.json
    ids = data.get('ids', [])

    if not isinstance(ids, list) or not ids:
        return ResponseUtil.error("IDs must be a non-empty list", status_code=400)

    try:
        devices_data = []
        for device_id in ids:
            device_ref = client.collection('devices').document(device_id).get()
            if device_ref.exists:
                device_info = device_ref.to_dict()

                # Retrieve lightIntensity and waterVol directly using device_id from Firebase RTDB
                rtdb_ref = db.reference(device_id)
                rtdb_data = rtdb_ref.get()

                if rtdb_data:
                    device_info['lightIntensity'] = rtdb_data.get('lightIntensity', -1)
                    device_info['waterVol'] = rtdb_data.get('waterVol', -1)

                devices_data.append(device_info)

        return ResponseUtil.success("Devices retrieved successfully", data=devices_data)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/<device_id>', methods=['GET'])
def device_detail(device_id):
    try:
        # Ambil data dokumen device dari Firestore
        device_ref = client.collection('devices').document(device_id).get()
        if device_ref.exists:
            device_data = device_ref.to_dict()

            # Menghitung total dokumen di dalam koleksi "photos"
            photos_ref = client.collection('devices').document(device_id).collection('photos')
            total_photo = len(list(photos_ref.stream()))

            # Menghitung total jadwal di dalam device_data['schedules']
            total_schedule = len(device_data.get('schedules', []))

            # Tambahkan data total ke response
            device_data['total_photo'] = total_photo
            device_data['total_schedule'] = total_schedule

            return ResponseUtil.success("Device details retrieved successfully", data=device_data)
        else:
            return ResponseUtil.error("Device not found", status_code=404)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/<device_id>/photos/<photo_id>', methods=['GET'])
def detail_photo(device_id, photo_id):
    try:
        photo_ref = client.collection('devices').document(device_id).collection('photos').document(photo_id).get()
        
        if photo_ref.exists:
            photo_data = photo_ref.to_dict()
            return ResponseUtil.success("Photo details retrieved successfully", data=photo_data)
        else:
            return ResponseUtil.error("Photo not found", status_code=404)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/<device_id>/photos', methods=['GET'])
def photos(device_id):
    try:
        photos_ref = client.collection('devices') \
                            .document(device_id) \
                            .collection('photos') \
                            .order_by('createdAt', direction=firestore.Query.DESCENDING) \
                            .get()

        photos_data = []

        for photo in photos_ref:
            # Menambahkan document ID ke dalam data photo
            photo_dict = photo.to_dict()
            photo_dict['id'] = photo.id  # Adding document ID
            photos_data.append(photo_dict)

        return ResponseUtil.success("Photos retrieved successfully", data=photos_data)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

def upload_photo_to_storage(photo, folder):
    if not folder:
        raise ValueError("Folder parameter is required")
    
    if not photo:
        raise ValueError("Photo file is required")

    try:
        # Generate a unique file name
        file_name = f"{folder}/{uuid.uuid4()}.jpg"
        bucket = storage.bucket("team-5c2-polije.appspot.com")  # Set bucket name secara eksplisit
        blob = bucket.blob(file_name)
        
        # Upload the file to Firebase Storage
        blob.upload_from_file(photo, content_type=photo.content_type)
        blob.make_public()

        # Get the URL for the uploaded photo
        photo_url = blob.public_url

        return photo_url
    except Exception as e:
        raise RuntimeError(f"Error while uploading photo: {str(e)}")

@device_bp.route('/device/add_photo', methods=['POST'])
def add_photo():
    data = request.files
    device_id = request.form.get('device_id')

    if not device_id:
        return ResponseUtil.error("Device ID parameter is required", data=None, status_code=400)
    
    if 'photo' not in data:
        return ResponseUtil.error("Photo file is required", data=None, status_code=400)

    photo = data['photo']

    try:
        # Mengunggah foto dan mendapatkan URL
        photoUrl = upload_photo_to_storage(photo, device_id)
        if photoUrl:
            new_photo = {
                "createdAt": SERVER_TIMESTAMP,
                "photoUrl": photoUrl,
                "updatedAt": SERVER_TIMESTAMP
            }
            # Menyimpan data new_photo ke Firestore
            client.collection('devices').document(device_id).collection('photos').add(new_photo)

            return ResponseUtil.success("Photo uploaded and saved successfully", data=None)
        else:
            return ResponseUtil.error("Failed to upload photo", data=None, status_code=500)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/add_photo_by_token', methods=['POST'])
def add_photo_by_token():
    data = request.files
    token = request.form.get('token')

    if not token:
        return ResponseUtil.error("Token parameter is required", data=None, status_code=400)
    
    if 'photo' not in data:
        return ResponseUtil.error("Photo file is required", data=None, status_code=400)

    photo = data['photo']

    try:
        # Cari device berdasarkan token
        device_ref = client.collection('devices').where('token', '==', token).limit(1).get()

        if not device_ref:
            return ResponseUtil.error("Device not found with the provided token", data=None, status_code=404)

        # Ambil device_id dari data device yang ditemukan
        device_data = device_ref[0].to_dict()
        device_id = device_ref[0].id

        # Mengunggah foto dan mendapatkan URL
        photoUrl = upload_photo_to_storage(photo, device_id)
        if photoUrl:
            new_photo = {
                "createdAt": SERVER_TIMESTAMP,
                "photoUrl": photoUrl,
                "updatedAt": SERVER_TIMESTAMP
            }
            # Menyimpan data new_photo ke Firestore di koleksi 'photos' pada perangkat yang ditemukan
            client.collection('devices').document(device_id).collection('photos').add(new_photo)

            return ResponseUtil.success("Photo uploaded and saved successfully", data=None)
        else:
            return ResponseUtil.error("Failed to upload photo", data=None, status_code=500)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/<device_id>/histories', methods=['GET'])
def histories(device_id):
    try:
        histories_ref = client.collection('devices') \
                               .document(device_id) \
                               .collection('histories') \
                               .order_by('createdAt', direction=firestore.Query.DESCENDING) \
                               .get()

        histories_data = []

        for history in histories_ref:
            # Menambahkan document ID ke dalam data history
            history_dict = history.to_dict()
            history_dict['id'] = history.id  # Adding document ID
            histories_data.append(history_dict)

        return ResponseUtil.success("Histories retrieved successfully", data=histories_data)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@device_bp.route('/device/add_history', methods=['POST'])
def add_history():
    data = request.json
    token = data.get('token')  # Menggunakan token
    schedule = data.get('schedule')
    is_manually = data.get('isManually')
    light_intensity = data.get('lightIntensity')
    water_vol = data.get('waterVol')

    if not token:
        return ResponseUtil.error("Token parameter is required", data=None, status_code=400)
    if schedule is None:
        return ResponseUtil.error("Schedule parameter is required", data=None, status_code=400)
    if is_manually is None:
        return ResponseUtil.error("isManually parameter is required", data=None, status_code=400)
    if light_intensity is None:
        return ResponseUtil.error("Light intensity parameter is required", data=None, status_code=400)
    if water_vol is None:
        return ResponseUtil.error("Water volume parameter is required", data=None, status_code=400)

    try:
        # Cari device berdasarkan token
        device_ref = client.collection('devices').where('token', '==', token).limit(1).get()

        if not device_ref:
            return ResponseUtil.error("Device not found with the provided token", data=None, status_code=404)

        # Ambil device_id dari data device yang ditemukan
        device_data = device_ref[0].to_dict()
        device_id = device_ref[0].id

        # Membuat history baru
        new_history = {
            "createdAt": SERVER_TIMESTAMP,
            "schedule": schedule,
            "isManually": True if is_manually == "1" else False,
            "lightIntensity": light_intensity,
            "waterVol": water_vol
        }

        # Menambahkan history ke dalam subkoleksi 'histories' dari device yang ditemukan
        client.collection('devices').document(device_id).collection('histories').add(new_history)

        return ResponseUtil.success("History added successfully", data=None)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)


@device_bp.route('/device/add_schedule', methods=['POST'])
def add_schedule():
    data = request.json
    device_id = data.get('device_id')
    hour = data.get('hour')

    if not device_id:
        return ResponseUtil.error("Device ID parameter is required", data=None, status_code=400)
    if not hour:
        return ResponseUtil.error("Hour parameter is required", data=None, status_code=400)
    
    try:
        # Ambil data schedules yang ada
        device_doc = client.collection('devices').document(device_id).get()
        if device_doc.exists:
            device_data = device_doc.to_dict()
            existing_schedules = device_data.get('schedules', {})

            # Ubah jam yang dimasukkan dan yang ada menjadi menit total untuk pengecekan
            new_hour_total = int(hour.split(':')[0]) * 60 + int(hour.split(':')[1])
            
            for existing_hour in existing_schedules.keys():
                existing_hour_total = int(existing_hour.split(':')[0]) * 60 + int(existing_hour.split(':')[1])
                
                # Cek apakah `new_hour_total` berada dalam rentang satu jam (60 menit) dari `existing_hour_total`
                if abs(new_hour_total - existing_hour_total) < 60:
                    return ResponseUtil.error(
                        f"Cannot add schedule. There is already a schedule within 60 minutes of {existing_hour}",
                        data=None,
                        status_code=400
                    )

            # Jika tidak ada konflik, tambahkan jadwal baru
            new_data = {
                f"schedules.{hour}": True,
                "updatedAt": SERVER_TIMESTAMP
            }
            client.collection('devices').document(device_id).update(new_data)

            return ResponseUtil.success("Schedule added successfully", data=None)
        else:
            return ResponseUtil.error("Device not found", data=None, status_code=404)

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)


@device_bp.route('/device/update_schedule', methods=['POST'])
def update_schedule():
    data = request.json
    device_id = data.get('device_id')
    hour = data.get('hour')
    status = data.get('status')

    if not device_id:
        return ResponseUtil.error("Device ID parameter is required", data=None, status_code=400)
    if not hour:
        return ResponseUtil.error("Hour parameter is required", data=None, status_code=400)
    if not status:
        return ResponseUtil.error("Status parameter is required", data=None, status_code=400)
    
    try:
        new_data = {
            f"schedules.{hour}": True if status == "1" else False,
            "updatedAt": SERVER_TIMESTAMP
        }
        client.collection('devices').document(device_id).update(new_data)
        
        return ResponseUtil.success("Schedule updated successfully", data=None)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)
    
@device_bp.route('/device/delete_schedule', methods=['POST'])
def delete_schedule():
    data = request.json
    device_id = data.get('device_id')
    hour = data.get('hour')

    if not device_id:
        return ResponseUtil.error("Device ID parameter is required", data=None, status_code=400)
    if not hour:
        return ResponseUtil.error("Hour parameter is required", data=None, status_code=400)
    
    try:
        # Hapus field schedule berdasarkan hour dan perbarui updatedAt
        update_data = {
            f"schedules.{hour}": firestore.DELETE_FIELD,
            "updatedAt": firestore.SERVER_TIMESTAMP
        }
        client.collection('devices').document(device_id).update(update_data)

        return ResponseUtil.success("Schedule deleted successfully", data=None)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)
from flask import Blueprint, jsonify, request
from ..utils.response_util import ResponseUtil
from firebase_admin import initialize_app, storage, credentials, firestore
from firebase_admin.firestore import SERVER_TIMESTAMP
from datetime import datetime

auth_bp = Blueprint('auth', __name__)
client = firestore.client()

@auth_bp.route('/auth', methods=['POST'])
def auth():
    data = request.json
    email = data.get('email')
    uid = data.get('uid')
    fcmToken = data.get('fcmToken')
    fullname = data.get('fullname')

    if not email:
        return ResponseUtil.error("Email parameter is required", data=None, status_code=400)
    if not uid:
        return ResponseUtil.error("UID parameter is required", data=None, status_code=400)
    if not fullname:
        return ResponseUtil.error("Fullname parameter is required", data=None, status_code=400)
    if not fcmToken:
        return ResponseUtil.error("FCM TOKEN parameter is required", data=None, status_code=400)

    try:
        user_ref = client.collection('users').where('email', '==', email).limit(1).get()

        if user_ref:
            user_doc = user_ref[0]
            user_ref_id = user_doc.id

            client.collection('users').document(user_ref_id).update({
                'fcmToken': fcmToken,
                'updatedAt': SERVER_TIMESTAMP
            })

            user_data = user_doc.to_dict()
            user_data['fcmToken'] = fcmToken

            return ResponseUtil.success("Autentikasi Berhasil", user_data)
        else:
            uid_check_ref = client.collection('users').document(uid).get()
            if uid_check_ref.exists:
                return ResponseUtil.error("UID already exists", status_code=400)

            user_ref = client.collection('users').document(uid)
            data['createdAt'] = SERVER_TIMESTAMP
            data['fcmToken'] = fcmToken
            data['devices'] = {}
            user_ref.set(data)

            user_ref = client.collection('users').where('email', '==', email).limit(1).get()
            if user_ref:
                user_data = user_ref[0].to_dict()
                return ResponseUtil.success("Autentikasi Berhasil", user_data)
            else:
                return ResponseUtil.error("Autentikasi Gagal", status_code=400)
    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@auth_bp.route('/add_device', methods=['POST'])
def addDevice():
    data = request.json
    email = data.get('email')
    token = data.get('token')

    if not email:
        return ResponseUtil.error("Email parameter is required", data=None, status_code=400)
    if not token:
        return ResponseUtil.error("Token parameter is required", data=None, status_code=400)
    
    try:
        # Cek apakah perangkat dengan token tertentu sudah ada
        device_ref = client.collection('devices').where('token', '==', token).limit(1).get()
        createdAt = SERVER_TIMESTAMP 
        
        if device_ref:
            device_data = device_ref[0].to_dict()
            device_id = device_ref[0].id
            my_device = {
                device_id: {
                    "name": device_data['name'],
                    "token": token,
                    "createdAt": createdAt
                }
            }

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            device_response = {
                device_id: {
                    "name": device_data['name'],
                    "createdAt": current_time,
                }
            }

            # Cari user berdasarkan email
            user_ref = client.collection('users').where('email', '==', email).limit(1).get()
            if not user_ref:
                return ResponseUtil.error("User not found", data=None, status_code=400)

            user_doc = user_ref[0]
            user_data = user_doc.to_dict()
            user_devices = user_data.get('devices', {})

            # Cek apakah device_id sudah ada di field devices
            if device_id in user_devices:
                return ResponseUtil.error("Device already exists", data=None, status_code=400)

            # Update field devices dengan my_device
            user_devices.update(my_device)
            client.collection('users').document(user_doc.id).update({'devices': user_devices})

            return ResponseUtil.success("Device added successfully", data=device_response)
        
        else:
            return ResponseUtil.error("Device not found", data=None, status_code=400)

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)
    
@auth_bp.route('/logout', methods=['POST'])
def logout():
    data = request.json
    email = data.get('email')

    if not email:
        return ResponseUtil.error("Email name parameter is required", data=None, status_code=400)

    try:
        user_ref = client.collection('users').where('email', '==', email)
        user_docs = user_ref.get()

        if user_docs:
            user_doc = user_docs[0]
            user_doc.reference.update({
                "fcmToken": "",
                "updatedAt": SERVER_TIMESTAMP
            })
        else:
            return ResponseUtil.error("User not found in Firestore", status_code=404)

        return ResponseUtil.success("User logged out successfully")

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

@auth_bp.route('/del_device', methods=['POST'])
def delete_device():
    data = request.json
    email = data.get('email')
    device_id = data.get('device_id')

    if not email:
        return ResponseUtil.error("Email parameter is required", data=None, status_code=400)
    if not device_id:
        return ResponseUtil.error("Device ID parameter is required", data=None, status_code=400)
    
    try:
        # Cari user berdasarkan email
        user_ref = client.collection('users').where('email', '==', email).limit(1).get()
        if not user_ref:
            return ResponseUtil.error("User not found", data=None, status_code=400)

        user_doc = user_ref[0]
        user_data = user_doc.to_dict()
        user_devices = user_data.get('devices', {})

        # Hapus device dari field devices
        del user_devices[device_id]

        # Update user dengan menghapus device dari field devices
        client.collection('users').document(user_doc.id).update({'devices': user_devices})

        return ResponseUtil.success("Device deleted successfully")

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)


@auth_bp.route('/notifications', methods=['GET'])
def histories():
    try:
        data = request.json
        email = data.get('email')

        if not email:
            return ResponseUtil.error("Email parameter is required", data=None, status_code=400)

        users_ref = client.collection('users').where('email', '==', email)
        user_doc = users_ref.get()

        if not user_doc:
            return ResponseUtil.error("No user found with the given email", data=None, status_code=404)

        notif_data = []

        for user in user_doc:
            notif_ref = user.reference.collection('notifications') \
                                     .order_by('sendAt', direction=firestore.Query.DESCENDING) \
                                     .get()

            for notif in notif_ref:
                notif_dict = notif.to_dict()
                notif_dict['id'] = notif.id 
                notif_data.append(notif_dict)

        return ResponseUtil.success("Notif retrieved successfully", data=notif_data)

    except Exception as e:
        return ResponseUtil.error(f"Internal Server Error: {str(e)}", status_code=500)

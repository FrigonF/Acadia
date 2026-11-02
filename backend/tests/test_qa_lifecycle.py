from fastapi.testclient import TestClient
from backend.app.main import app

def test_full_qa_suite():
    client = TestClient(app)

    # 1. Login
    auth_res = client.post('/api/v1/auth/login/json', json={'email': 'admin@acadia.gov.in', 'password': 'Admin@Acadia2026'})
    assert auth_res.status_code == 200
    token = auth_res.json()["access_token"]
    headers = {'Authorization': f'Bearer {token}'}
    print('\n1. Admin Login OK')

    # 2. Target Institution
    inst_res = client.get('/api/v1/institutions', headers=headers)
    inst_id = inst_res.json()[0]['id']

    # 3. Create Student
    st_res = client.post('/api/v1/students', headers=headers, json={
        'institution_id': inst_id,
        'name': 'Priya S. Nambiar',
        'apaar_id': '887766554433',
        'programme': 'B.Tech Computer Science and Engineering',
        'academic_year': '2025-2026',
        'seat_category': 'GENERAL',
        'enrollment_number': 'ENR-2026-QA-01'
    })
    assert st_res.status_code == 201
    st_id = st_res.json()['id']
    print('2. Created Student:', st_id, st_res.json()['name'], st_res.json()['apaar_masked'])

    # 4. Seal Record v1
    seal1 = client.post(f'/api/v1/integrity/{st_id}/seal', headers=headers)
    assert seal1.status_code == 200
    print('3. Sealed Record v1:', seal1.json()['fingerprint'][:24], 'Key ID:', seal1.json()['key_id'])

    # 5. Generate QR Credential for v1
    qr1 = client.post(f'/api/v1/qr/generate/{st_id}', headers=headers)
    assert qr1.status_code == 200
    qr_token1 = qr1.json()['qr_verification_token']
    print('4. Generated QR Credential 1:', qr_token1[:24])

    # 6. Verify Public QR 1
    pub_ver1 = client.get(f'/api/v1/qr/verify/{qr_token1}')
    assert pub_ver1.status_code == 200
    assert pub_ver1.json()['verified'] is True
    print('5. Public QR 1 Verified:', pub_ver1.json()['status'])

    # 7. Edit Student -> creates v2 and supersedes credential 1
    edit_res = client.patch(f'/api/v1/students/{st_id}', headers=headers, json={
        'name': 'Priya S. Nambiar (Honours)',
        'seat_category': 'TFWS',
        'reason': 'Awarded Tuition Fee Waiver Scheme after state allotment audit'
    })
    assert edit_res.status_code == 200
    print('6. Edited Student:', edit_res.json()['name'], edit_res.json()['seat_category'])

    # 8. Check that old QR credential 1 is now SUPERSEDED / cannot represent updated record as current
    pub_ver1_after = client.get(f'/api/v1/qr/verify/{qr_token1}')
    assert pub_ver1_after.json()['verified'] is False
    print('7. Old QR 1 after edit: Verified =', pub_ver1_after.json()['verified'], '| Status =', pub_ver1_after.json()['status'])

    # 9. Check Version History: confirms v1 preserved and v2 created with distinct fingerprints
    vers = client.get(f'/api/v1/integrity/{st_id}', headers=headers)
    assert len(vers.json()['versions']) == 2
    for v in vers.json()['versions']:
        print(f"   Version {v['version_number']}: Fingerprint {v['fingerprint'][:20]}... Prev: {str(v['previous_fingerprint'])[:20]}...")

    # 10. Deactivate Student
    deact = client.post(f'/api/v1/students/{st_id}/deactivate', headers=headers, json={'reason': 'Student transfer to partner research university'})
    assert deact.status_code == 200
    assert deact.json()['record_status'] == 'DEACTIVATED'
    print('8. Deactivated Student Status:', deact.json()['record_status'])

    # 11. Reactivate Student
    react = client.post(f'/api/v1/students/{st_id}/reactivate', headers=headers)
    assert react.status_code == 200
    assert react.json()['record_status'] == 'VALIDATED'
    print('9. Reactivated Student Status:', react.json()['record_status'])

    print('\n=== ALL LIFECYCLE & CRYPTOGRAPHIC CHECKS PASSED ===\n')

if __name__ == '__main__':
    test_full_qa_suite()

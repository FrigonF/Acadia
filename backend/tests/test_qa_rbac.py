from fastapi.testclient import TestClient
from backend.app.main import app

def test_rbac_and_tenant_isolation():
    client = TestClient(app)

    # 1. Login as External Verifier (read-only role)
    ext_auth = client.post('/api/v1/auth/login/json', json={'email': 'verifier@external-corp.com', 'password': 'Verify@External2026'}).json()
    ext_headers = {'Authorization': f'Bearer {ext_auth["access_token"]}'}

    # 2. Login as Pune Institution Admin
    pune_auth = client.post('/api/v1/auth/login/json', json={'email': 'admin@mitr.ac.in', 'password': 'Pune@Inst2026'}).json()
    pune_headers = {'Authorization': f'Bearer {pune_auth["access_token"]}'}
    pune_inst_id = pune_auth["institution_id"]

    # 3. Login as Delhi Institution Admin
    delhi_auth = client.post('/api/v1/auth/login/json', json={'email': 'admin@diaet.edu.in', 'password': 'Delhi@Inst2026'}).json()
    delhi_headers = {'Authorization': f'Bearer {delhi_auth["access_token"]}'}
    delhi_inst_id = delhi_auth["institution_id"]

    # --- Test 1: External Verifier blocked from creating students (Forbidden) ---
    forbidden_create = client.post('/api/v1/students', headers=ext_headers, json={
        'institution_id': delhi_inst_id,
        'name': 'Unauthorized Student',
        'apaar_id': '111122223333',
        'programme': 'B.Tech Computer Science and Engineering',
        'academic_year': '2025-2026'
    })
    assert forbidden_create.status_code == 403
    print('Test 1 (External Verifier create attempt blocked):', forbidden_create.status_code)

    # Get a Delhi student
    delhi_students = client.get('/api/v1/students', headers=delhi_headers).json()
    assert len(delhi_students) > 0
    delhi_student_id = delhi_students[0]['id']

    # --- Test 2: External Verifier blocked from deactivating students ---
    ext_deact = client.post(f'/api/v1/students/{delhi_student_id}/deactivate', headers=ext_headers, json={'reason': 'hack attempt'})
    assert ext_deact.status_code == 403
    print('Test 2 (External Verifier deactivation blocked):', ext_deact.status_code)

    # --- Test 3: Pune Admin blocked from viewing Delhi student by ID ---
    pune_cross_view = client.get(f'/api/v1/students/{delhi_student_id}', headers=pune_headers)
    assert pune_cross_view.status_code == 403
    print('Test 3 (Pune Admin cross-institution access blocked):', pune_cross_view.status_code)

    # --- Test 4: Pune Admin blocked from modifying Delhi student ---
    pune_cross_edit = client.patch(f'/api/v1/students/{delhi_student_id}', headers=pune_headers, json={
        'name': 'Hacked Name',
        'reason': 'Cross institution breach attempt'
    })
    assert pune_cross_edit.status_code == 403
    print('Test 4 (Pune Admin cross-institution edit blocked):', pune_cross_edit.status_code)

    # --- Test 5: Pune Admin blocked from creating record under Delhi institution ---
    pune_cross_create = client.post('/api/v1/students', headers=pune_headers, json={
        'institution_id': delhi_inst_id,
        'name': 'Spoofed Student',
        'apaar_id': '444455556666',
        'programme': 'B.Tech Computer Science and Engineering',
        'academic_year': '2025-2026'
    })
    assert pune_cross_create.status_code == 403
    print('Test 5 (Pune Admin cross-institution student creation blocked):', pune_cross_create.status_code)

    print('\n=== ALL 5 ROLE & TENANT ISOLATION TESTS PASSED ===\n')

if __name__ == '__main__':
    test_rbac_and_tenant_isolation()

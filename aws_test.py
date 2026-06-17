# aws_test.py -- verifies S3 upload and presigned URL generation

from aws_connect import upload_resume, get_presigned_url

# Create a small dummy PDF-like payload
dummy_bytes = b"%PDF-1.4 dummy resume content for TalentMap S3 test"
filename = "test_resume.pdf"

print("Uploading test file to S3...")
key = upload_resume(dummy_bytes, filename)
print(f"  [OK] Uploaded successfully")
print(f"  S3 Key: {key}")

print("\nGenerating presigned URL...")
url = get_presigned_url(key, expires=300)
print(f"  [OK] Presigned URL generated (valid for 5 minutes)")
print(f"  URL: {url}")

print("\n[OK] AWS S3 connection test passed!")

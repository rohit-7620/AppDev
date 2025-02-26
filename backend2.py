from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import pyodbc
import os
from azure.storage.blob import BlobServiceClient
from azure.ai.vision import VisionClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.ml import MLClient

app = FastAPI()

# Azure SQL Database Connection
server = 'rohit108.database.windows.net'
database = 'crimeDB'
username = 'adminCrime'
password = os.getenv("DB_PASSWORD", "Pass@123")  # Use environment variables for security
driver = '{ODBC Driver 17 for SQL Server}'
conn_str = f'DRIVER={driver};SERVER={server};PORT=1433;DATABASE={database};UID={username};PWD={password}'

# Azure Blob Storage Configuration
storage_account_name = "crimeappstorage"
storage_account_key = os.getenv("STORAGE_ACCOUNT_KEY", "your_storage_key")
container_name = "crime"
blob_service_client = BlobServiceClient(account_url=f"https://{storage_account_name}.blob.core.windows.net", credential=storage_account_key)
container_client = blob_service_client.get_container_client(container_name)

# Azure AI Services (Cognitive Services & Machine Learning)
vision_endpoint = os.getenv("VISION_ENDPOINT", "https://your-cognitive-service.cognitiveservices.azure.com")
vision_key = os.getenv("VISION_KEY", "your_vision_key")
vision_client = VisionClient(vision_endpoint, AzureKeyCredential(vision_key))

ml_workspace = "your-ml-workspace"
ml_client = MLClient(AzureKeyCredential("your_ml_key"), subscription_id="your_subscription_id", resource_group="crime-app-rg", workspace_name=ml_workspace)

class CrimeReport(BaseModel):
    title: str
    description: str
    location: str

@app.post("/report")
def report_crime(report: CrimeReport):
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO CrimeReports (title, description, location) VALUES (?, ?, ?)", 
                       (report.title, report.description, report.location))
        conn.commit()
        cursor.close()
        conn.close()
        return {"message": "Crime reported successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
def upload_image(file: UploadFile = File(...)):
    try:
        blob_client = container_client.get_blob_client(file.filename)
        with file.file as f:
            blob_client.upload_blob(f, overwrite=True)
        return {"message": "Image uploaded successfully", "url": f"https://{storage_account_name}.blob.core.windows.net/{container_name}/{file.filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze_image")
def analyze_image(file: UploadFile = File(...)):
    try:
        image_data = file.file.read()
        analysis = vision_client.analyze_image(image_data, features=["Objects", "Tags"])
        return {"tags": [tag.name for tag in analysis.tags]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict_crime")
def predict_crime(report: CrimeReport):
    try:
        prediction = ml_client.online_endpoints.invoke(endpoint_name="crime-prediction", json={
            "title": report.title,
            "description": report.description,
            "location": report.location
        })
        return {"prediction": prediction}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reports")
def get_reports():
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute("SELECT title, description, location FROM CrimeReports")
        reports = cursor.fetchall()
        cursor.close()
        conn.close()
        return [{"title": row[0], "description": row[1], "location": row[2]} for row in reports]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

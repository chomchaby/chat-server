# Chat Server
## 
Create python environment
```bash
python -m venv venv
```
Activate python environment
```bash
.\venv\Scripts\activate
```
Install python pip
```bash
python -m pip install --upgrade pip
```
Install dependencies: 
```bash
python -m pip install -r requirements.txt
```
Create a .env file with the following content:
```bash
# .env
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here
MONGO_URI=your_mongodb_uri_here
```

To run the server application:
```bash
python app.py
```
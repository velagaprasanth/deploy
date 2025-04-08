# House Cleaning App

A modern web application for managing house cleaning photos.

## Features

- Upload and manage cleaning photos
- Responsive design for all devices
- Secure file handling
- Modern UI with Bootstrap 5
- Easy-to-use interface

## Setup

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python app.py
   ```
5. Open your browser and navigate to `http://localhost:5000`

## Usage

1. Click the "Upload Image" button to select and upload a photo
2. View your uploaded photos in the grid below
3. Click the delete button (trash icon) to remove a photo
4. Photos are automatically sorted by upload date (newest first)

## Requirements

- Python 3.8 or higher
- Modern web browser
- 16MB maximum file size for uploads
- Supported image formats: PNG, JPG, JPEG, GIF

## Security

- Files are stored with unique identifiers
- File extensions are validated
- Filenames are sanitized
- Maximum file size is enforced

## License

MIT License 
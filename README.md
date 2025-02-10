# InboXpert - AI Email Cleaner
## Demo
🔗 [View Demo Video](https://twitter.com/SumitPaul18_9/status/1889016485345153313)

## Local Installation Steps

1. **Install Ollama**
   - Visit [Ollama's website](https://ollama.ai) and download the installer for your OS
   - Install Ollama on your system

2. **Install Python Requirements**
   ```bash
   pip install -r requirements.txt
   ```

3. **Download Llama Model**
   ```bash
   ollama pull llama3.1:latest
   ```

4. **Get Google OAuth Credentials**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select existing one
   - Enable Gmail API
   - Create OAuth 2.0 credentials
   - Download the credentials and save as `credentials.json` in the project directory

5. **Start Ollama Server**
   ```bash
   ollama serve
   ```

6. **Run the Application**
   ```bash
   streamlit run main.py
   ```

7. **Access the Application**
   - Open http://localhost:8501 in your browser
   - Click "Authenticate with Google" when prompted
   - Complete the Google authentication process
   - Start using InboXpert!

## Notes
- Make sure Ollama is running before starting the application
- The first time you run the application, you'll need to authenticate with Google
- Your emails are processed locally and are not stored anywhere 


## Contributing Guidelines

We welcome contributions to InboXpert! Please follow these steps:

1. **Fork the repository.**
2. **Create a new branch** for your feature or bug fix.
3. **Make your changes** with clear commit messages.
4. **Push your branch** and open a pull request.
5. **Ensure your code** meets the project's coding standards and includes appropriate tests.

For any questions or clarifications, please open an issue before submitting your pull request.

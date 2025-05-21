# Digital Legacy Platform

A secure platform for managing and transferring digital assets after death.

## Features

- **User Authentication**
  - Email/Password login
  - MetaMask wallet login
  - Secure JWT token-based authentication

- **Asset Management**
  - Upload and manage digital assets
  - Categorize assets (documents, photos, videos, etc.)
  - Set transfer instructions for each asset

- **Wallet Integration**
  - Connect MetaMask wallet
  - Secure wallet-based authentication
  - Support for Ethereum-based transactions

- **User Profile**
  - Update profile information
  - Manage connected wallets
  - View asset statistics

## Recent Updates

- **Wallet Login Fix**
  - Fixed wallet login logic to allow users to log in with their wallet without requiring an email
  - Improved backend logic to differentiate between wallet login and wallet connect

- **UI Improvements**
  - Enhanced dashboard layout
  - Improved asset management interface
  - Better error handling and user feedback

## Getting Started

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/digital-legacy-platform.git
   cd digital-legacy-platform
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   - Create a `.env` file in the root directory
   - Add the following variables:
     ```
     SECRET_KEY=your_secret_key
     DATABASE_URL=your_database_url
     ```

4. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Access the application**
   - Open your browser and go to `http://localhost:8000`

## Contributing

We welcome contributions! If you'd like to contribute to this project, please follow these steps:

1. **Fork the repository**
2. **Create a new branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes**
4. **Commit your changes**
   ```bash
   git commit -m "Add your feature"
   ```
5. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```
6. **Create a Pull Request**

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

If you have any questions or suggestions, feel free to open an issue or contact us at [your-email@example.com](mailto:your-email@example.com).

---

**Thank you for your interest in the Digital Legacy Platform! We look forward to your contributions!** 
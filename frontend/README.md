# Frontend - Procurement Garage

Next.js frontend application for the Spend Analysis Agent with Azure Copilot Studio integration.

## Features

- 🏠 **Landing Page**: Card-based navigation for Taxonomy and Classification features
- 📊 **Taxonomy Analysis**: Upload Excel files for spend taxonomy classification
- 💬 **AI Chat**: Integrated Azure Copilot Studio via Direct Line for contextual insights
- 🎨 **Modern UI**: Clean, professional design with Tailwind CSS

## Architecture

```
Frontend (Vercel/Local)
    ↓
    ├─► GET /get-token → Azure Function
    │   (Gets temporary Direct Line token)
    │
    ├─► POST /ProcessExcelFile → Azure Function
    │   (Processes spend analysis)
    │
    └─► Direct Line WebSocket → Azure Bot Service
        (Chat with AI using secure token)
```

## Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

Copy `.env.local.example` to `.env.local` and update:

```bash
NEXT_PUBLIC_API_URL=http://localhost:7071/api
```

For production, use your Azure Function URL.

### 3. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Sidebar.tsx        # Dark sidebar with session info
│   │   └── FileUpload.tsx     # Drag-and-drop file upload
│   ├── pages/
│   │   ├── _app.tsx           # Next.js app wrapper
│   │   ├── index.tsx          # Landing page with cards
│   │   └── taxonomy.tsx       # Main taxonomy analysis page
│   ├── lib/
│   │   └── api.ts             # API client for Azure Functions
│   └── styles/
│       └── globals.css        # Global styles and design tokens
├── public/
│   └── Spend_Taxonomy.xlsx    # Default taxonomy dictionary
├── package.json
├── tsconfig.json
└── tailwind.config.js
```

## Key Components

### Landing Page (`/`)
Two-card interface:
- **Realizar Taxonomia** (Active): Navigate to taxonomy analysis
- **Classificação** (Disabled): Future feature

### Taxonomy Page (`/taxonomy`)
- **Sidebar**: Shows current session (filename, sector)
- **File Upload**: Drag-and-drop or click to upload Excel/CSV
- **Chat Interface**: Web Chat with Azure Copilot Studio after analysis
- **Sector Selection**: Choose between Varejo/Educacional

## Backend Integration

The frontend connects to Azure Functions:

1. **`/get-token`**: Securely exchange Direct Line secret for temporary token
2. **`/ProcessExcelFile`**: Upload and classify spend data

## Deployment

### Vercel (Recommended)

1. Push code to GitHub
2. Import project in Vercel
3. Set environment variables:
   - `NEXT_PUBLIC_API_URL`: Your Azure Function URL

```bash
npm run build
```

### Manual Build

```bash
npm run build
npm start
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Azure Function endpoint | `https://your-app.azurewebsites.net/api` |

## Color Palette

Matching the design mockup:

- Primary Blue: `#1e5a8e`
- Sidebar Dark: `#2c3e50`
- Sidebar Light: `#34495e`
- Text Primary: `#212529`
- Text Secondary: `#6c757d`

## Dependencies

- **Next.js 14**: React framework
- **TypeScript**: Type safety
- **Tailwind CSS**: Utility-first styling
- **botframework-webchat**: Azure Bot integration
- **axios**: HTTP client

## Next Steps

- [ ] Add loading states and error handling
- [ ] Implement download results functionality
- [ ] Add analytics visualization
- [ ] Enable multi-file batch processing
- [ ] Add user authentication

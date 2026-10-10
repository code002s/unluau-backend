import React, { useState } from 'react';
import Editor from "@monaco-editor/react";
import axios from 'axios';

export default function DecompilerWorkspace() {
    const [bytecode, setBytecode] = useState('');
    const [source, setSource] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const runDecompile = async () => {
        setIsLoading(true);
        try {
            const response = await axios.post('http://localhost:3000/decompile', {
                bytecode: btoa(bytecode), // Simple base64 for demo
                dialect: 'auto'
            });
            setSource(response.data.source);
        } catch (e) {
            alert('Error: ' + e.message);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div style={{ display: 'flex', height: '100vh', fontFamily: 'sans-serif' }}>
            {/* Sidebar: Input */}
            <div style={{ width: '30%', borderRight: '1px solid #ccc', padding: '20px', display: 'flex', flexDirection: 'column' }}>
                <h2>unluac-rs Workspace</h2>
                <p>Paste Base64 Bytecode:</p>
                <textarea
                    style={{ flex: 1, marginBottom: '10px', padding: '10px' }}
                    value={bytecode}
                    onChange={(e) => setBytecode(e.target.value)}
                />
                <button
                    onClick={runDecompile}
                    disabled={isLoading}
                    style={{ padding: '10px', cursor: 'pointer', background: '#007acc', color: 'white', border: 'none', borderRadius: '4px' }}
                >
                    {isLoading ? 'Decompiling...' : 'Decompile →'}
                </button>
            </div>

            {/* Main: Editor */}
            <div style={{ width: '70%', position: 'relative' }}>
                <Editor
                    height="100%"
                    defaultLanguage="lua"
                    theme="vs-dark"
                    value={source}
                    options={{ readOnly: false, minimap: { enabled: false } }}
                />
            </div>
        </div>
    );
}

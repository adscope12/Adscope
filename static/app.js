// AdScope App JavaScript
// This file contains shared JavaScript functionality

// File upload handling
function handleDragOver(e) {
    e.preventDefault();
    if (e.currentTarget) {
        e.currentTarget.classList.add('dragover');
    }
}

function handleDragLeave(e) {
    if (e.currentTarget) {
        e.currentTarget.classList.remove('dragover');
    }
}

function handleDrop(e) {
    e.preventDefault();
    if (e.currentTarget) {
        e.currentTarget.classList.remove('dragover');
    }
    const files = e.dataTransfer.files;
    if (files.length > 0 && document.getElementById('file-input')) {
        document.getElementById('file-input').files = files;
        handleFile(files[0]);
    }
}

function handleFileSelect(e) {
    if (e.target.files && e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
}

function handleFile(file) {
    const validExtensions = ['csv', 'xlsx', 'xls'];
    const extension = file.name.split('.').pop().toLowerCase();
    
    if (!validExtensions.includes(extension)) {
        alert('Please upload a CSV or XLSX file');
        return;
    }
    
    const fileNameEl = document.getElementById('file-name');
    const fileInfoEl = document.getElementById('file-info');
    const btnAnalyze = document.getElementById('btn-analyze');
    
    if (fileNameEl) fileNameEl.textContent = file.name;
    if (fileInfoEl) fileInfoEl.classList.remove('hidden');
    if (btnAnalyze) btnAnalyze.disabled = false;
}

function clearFile() {
    const fileInput = document.getElementById('file-input');
    const fileInfoEl = document.getElementById('file-info');
    const btnAnalyze = document.getElementById('btn-analyze');
    
    if (fileInput) fileInput.value = '';
    if (fileInfoEl) fileInfoEl.classList.add('hidden');
    if (btnAnalyze) btnAnalyze.disabled = true;
}

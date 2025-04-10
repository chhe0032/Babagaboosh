const chatHistory = document.getElementById("chat-history");
const userInput = document.getElementById("user-input");
const sendButton = document.getElementById("send-button");
const recordButton = document.getElementById("record-button");
const systemMessageSelect = document.getElementById("system-message-select");
const updateSystemMessageButton = document.getElementById("update-system-message-button");

let isRecording = false;
let mediaRecorder;
let audioChunks;
let twitchRefreshInterval;

// Function to fetch and populate system message options
async function fetchSystemMessages() {
    try {
        console.log("Fetching system message options...");
        const response = await fetch("/get_system_messages");
        
        if (!response.ok) {
            throw new Error(`Failed to fetch system message options. Status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log("System messages data:", data);
        
        // Clear existing options
        systemMessageSelect.innerHTML = "";
        
        if (!data.system_messages || data.system_messages.length === 0) {
            // Add a default option if no files found
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "No system messages found";
            systemMessageSelect.appendChild(option);
            console.warn("No system message files found");
            
            if (data.error) {
                console.error("Server reported error:", data.error);
            }
        } else {
            // Add new options based on server response
            data.system_messages.forEach(file => {
                const option = document.createElement("option");
                option.value = file;
                
                // Create a more user-friendly display name
                let displayName = file.replace(".txt", "");
                
                // Special handling for system_message files
                if (displayName === "system_message") {
                    displayName = "Default System Message";
                } else if (displayName.startsWith("system_message_")) {
                    // For numbered system messages like system_message_2.txt
                    const number = displayName.replace("system_message_", "");
                    displayName = `System Message ${number}`;
                }
                
                option.textContent = displayName;
                systemMessageSelect.appendChild(option);
            });
            
            console.log("System message options loaded successfully");
        }
    } catch (error) {
        console.error("Error fetching system message options:", error);
        
        // Clear existing options
        systemMessageSelect.innerHTML = "";
        
        // Add an error option
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Error loading options";
        systemMessageSelect.appendChild(option);
        
        // Show alert with more details
        alert(`Failed to load system message options: ${error.message}`);
    }
}

// Function to update the system message
async function updateSystemMessage() {
    const selectedFile = systemMessageSelect.value;

    try {
        const response = await fetch("/update_system_message", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ file: selectedFile }),
        });

        if (!response.ok) {
            throw new Error("Failed to update system message.");
        }

        const data = await response.json();
        alert(data.message);  // Notify the user that the system message was updated

    } catch (error) {
        console.error("Error:", error);
        alert("Failed to update system message.");
    }
}

// Function to send the user's prompt and optional image to the backend
async function sendPrompt() {
    const prompt = userInput.value.trim();
    if (!prompt) {
        alert("Please enter a prompt!");
        return;
    }

    // Add the user's prompt to the chat history
    chatHistory.innerHTML += `<p><strong>You:</strong> ${prompt}</p>`;

    // Prepare form data (supports both text and file)
    const formData = new FormData();
    formData.append('prompt', prompt);
    
    // Check if there's an image preview (from drag & drop)
    const imageFile = document.getElementById('fileElem').files[0];
    if (imageFile) {
        formData.append('image', imageFile);
    }

    // Send the data to the backend
    try {
        const response = await fetch("/process_input", {
            method: "POST",
            body: formData, // No Content-Type header for FormData!
        });

        if (!response.ok) {
            throw new Error("Failed to get response from the server.");
        }

        const data = await response.json();
        const llmResponse = data.response;
        
        // Add the LLM's response to the chat history
        chatHistory.innerHTML += `<p><strong>LLM:</strong> ${llmResponse}</p>`;
        
        // Clear the image preview if exists
        if (imageFile) {
            document.getElementById('preview').style.display = 'none';
            document.getElementById('fileElem').value = '';
        }

    } catch (error) {
        console.error("Error:", error);
        chatHistory.innerHTML += `<p><strong>Error:</strong> Failed to get a response.</p>`;
    }

    // Clear the input field
    userInput.value = "";
}

function startRecording() {
    audioChunks = [];
    
    // Request access to the microphone
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            
            // Event handler for when data is available
            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                }
            };
            
            // Event handler for when recording stops
            mediaRecorder.onstop = async () => {
                // Create a blob from all the chunks
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                
                // Create a FormData object to send to the server
                const formData = new FormData();
                formData.append('audio', audioBlob, 'recording.webm');
                formData.append('use_browser_audio', 'true');
                
                // Add recording status to chat history
                chatHistory.innerHTML += `<p><strong>You:</strong> [Audio recording]</p>`;
                
                try {
                    // Send the audio recording to the server
                    const response = await fetch('/process_audio', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (!response.ok) {
                        throw new Error(`Server responded with ${response.status}`);
                    }
                    
                    const data = await response.json();
                    
                    // Add the transcribed text and AI response to the chat history
                    chatHistory.innerHTML += `<p><em>Transcribed:</em> ${data.transcribed_text}</p>`;
                    chatHistory.innerHTML += `<p><strong>LLM:</strong> ${data.response}</p>`;
                    
                    // Play the audio response if available
                    if (data.audio_url) {
                        playAudioInBrowser(data.audio_url);
                    }
                    
                } catch (error) {
                    console.error('Error processing audio:', error);
                    chatHistory.innerHTML += `<p><strong>Error:</strong> Failed to process audio recording.</p>`;
                }
            };
            
            // Start recording
            mediaRecorder.start();
        })
        .catch(error => {
            console.error('Error accessing microphone:', error);
            alert('Error accessing microphone. Please check your browser permissions.');
            recordButton.textContent = "Start Recording";
            isRecording = false;
        });
}

async function playAudioInBrowser(audioUrl) {
    try {
        console.log("Attempting to play audio from URL:", audioUrl);
        
        // Fetch the audio file as a Blob
        const audioResponse = await fetch(audioUrl);
        if (!audioResponse.ok) {
            throw new Error(`Failed to fetch audio file: ${audioResponse.status} ${audioResponse.statusText}`);
        }
        
        const audioBlob = await audioResponse.blob();
        const audioObjectURL = URL.createObjectURL(audioBlob);
        
        // Create and configure audio element
        const audio = new Audio(audioObjectURL);
        
        // Set up promise to track when audio starts playing
        const playPromise = new Promise((resolve, reject) => {
            audio.oncanplaythrough = () => {
                console.log("Audio can play through, starting playback");
                const playAttempt = audio.play();
                if (playAttempt !== undefined) {
                    playAttempt
                        .then(() => {
                            console.log("Audio playback started successfully");
                            resolve();
                        })
                        .catch(error => {
                            console.error("Audio playback failed:", error);
                            reject(error);
                        });
                } else {
                    resolve(); // For browsers that don't return a promise from play()
                }
            };
            
            audio.onerror = (e) => {
                console.error("Error loading audio:", e);
                reject(new Error("Failed to load audio"));
            };
        });
        
        // Clean up the object URL when done to avoid memory leaks
        audio.onended = () => {
            console.log("Audio playback completed");
            URL.revokeObjectURL(audioObjectURL);
        };
        
        return playPromise;
    } catch (error) {
        console.error("Error in playAudioInBrowser:", error);
        throw error;
    }
}

async function fetchLLMResponse(prompt) {
    try {
        const response = await fetch("/process_input", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ prompt: prompt }),
        });

        if (!response.ok) {
            throw new Error("Failed to get response from the server.");
        }

        const data = await response.json();
        return data.response;  // Assuming the backend returns the LLM response in "response" field
    } catch (error) {
        console.error("Error:", error);
        return "Error fetching LLM response.";
    }
}


recordButton.addEventListener("click", () => {
    if (isRecording) {
        mediaRecorder.stop();
        recordButton.textContent = "Start Recording";
        isRecording = false;
    } else {
        startRecording();
        recordButton.textContent = "Stop Recording";
        isRecording = true;
    }
});

sendButton.addEventListener("click", sendPrompt);

updateSystemMessageButton.addEventListener("click", updateSystemMessage);

// Allow pressing Enter to send the prompt
userInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
        sendPrompt();
    }
});

// Load system message options when the page loads
document.addEventListener("DOMContentLoaded", fetchSystemMessages);

// Test for playing any audio in Browser
async function requestAndPlayAudio() {
    try {
        const response = await fetch("/play_audio", { method: "GET" });
        if (!response.ok) {
            throw new Error(`Failed to fetch audio: ${response.status} ${response.statusText}`);
        }
        
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        
        await playAudioInBrowser(audioUrl); // Calls your existing function
    } catch (error) {
        console.error("Error requesting and playing audio:", error);
    }
}

const dropArea = document.getElementById("drop-area");
const fileInput = document.getElementById("fileElem");
const preview = document.getElementById("preview");

dropArea.addEventListener("click", () => fileInput.click());

dropArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropArea.style.backgroundColor = "#eee";
});

dropArea.addEventListener("dragleave", () => {
    dropArea.style.backgroundColor = "#f9f9f9";
});

dropArea.addEventListener("drop", (e) => {
    e.preventDefault();
    dropArea.style.backgroundColor = "#f9f9f9";
    if (e.dataTransfer.files.length) {
        handleFiles(e.dataTransfer.files);
    }
});

function handleFiles(files) {
    const file = files[0];
    if (file && file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (e) => {
            preview.src = e.target.result;
            preview.style.display = "block";
        };
        reader.readAsDataURL(file);
    }
}
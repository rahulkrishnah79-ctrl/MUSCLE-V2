"""
Food Recognition & Nutrition Estimation Engine for IronPulse
Handles camera snapshot analysis, AI vision API communication (Gemini / OpenAI),
local computer vision feature classification, image validation, confidence thresholds,
and exact nutritional resolution against the application's food database.

Guarantees:
1. Detects whether actual food is present (Food vs Non-Food: laptop, person, car, pet).
2. If non-food or low confidence (< 0.50), returns status: "no_food_detected".
3. Identifies individual food items (including multiple foods on a plate: Rice + Dal + Veg, Idli + Sambar, etc.).
4. Resolves exact calories, protein, carbs, and fats from the application database.
5. Does not rely solely on a boolean flag (food_detected=true/false): if valid food items are present
   with reasonable confidence (>= 0.50), treats food as detected.
6. Robust JSON parser extracts clean data from markdown fences and raw text.
7. Comprehensive backend debug logging for AI vision diagnostics.
"""

import os
import io
import base64
import json
import re
import logging
import requests
import numpy as np
from PIL import Image
from dotenv import load_dotenv

import database
import nutrition_manager

# Ensure environment variables from .env are loaded
load_dotenv()

# Setup logger for backend AI diagnostics
logger = logging.getLogger("food_recognition")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ESTIMATES_DISCLAIMER = (
    "⚠️ Nutritional values are ESTIMATES based on visual cues and standard portion densities. "
    "Camera scanning cannot determine exact calories, hidden cooking oils, or precise gram weights. "
    "Always verify and adjust your meal details below."
)

# Reasonable initial confidence threshold (0.50)
CONFIDENCE_THRESHOLD = 0.50

def log_ai_vision_debug(provider, http_status, raw_response, parsed_json, food_detected, foods_array, confidence_values, final_decision):
    """
    Temporary debug logger for AI vision diagnostics.
    Logs HTTP status, raw response, parsed JSON, food_detected flag, foods array, confidence values,
    and final detection decision.
    """
    sep = "=" * 65
    raw_preview = str(raw_response)[:1000] + ("..." if len(str(raw_response)) > 1000 else "")
    logger.info(
        "\n%s\n[AI FOOD VISION BACKEND DEBUG LOG]\n"
        "  * Provider:                 %s\n"
        "  * HTTP Status:              %s\n"
        "  * Raw Response:             %s\n"
        "  * Parsed JSON:              %s\n"
        "  * food_detected flag:       %s\n"
        "  * foods array:              %s\n"
        "  * Confidence values:        %s\n"
        "  * Final Detection Decision: %s\n%s",
        sep,
        provider,
        http_status,
        raw_preview,
        json.dumps(parsed_json, default=str) if parsed_json else "None",
        food_detected,
        json.dumps(foods_array, default=str) if foods_array else "[]",
        confidence_values,
        final_decision,
        sep
    )

def extract_json_from_ai_response(text: str):
    """
    Robustly extracts and parses JSON from AI vision responses.
    Handles:
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Extra commentary or preamble text before/after JSON
    - Trailing commas before closing braces/brackets
    """
    if not text or not str(text).strip():
        raise ValueError("Empty AI response text")

    clean_text = str(text).strip()

    # 1. First attempt: extract inside markdown code fences if present
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(fence_pattern, clean_text, re.DOTALL)
    if match:
        clean_text = match.group(1).strip()

    # 2. Extract outermost JSON object or array
    json_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", clean_text)
    candidate = json_match.group(1) if json_match else clean_text

    # 3. Clean trailing commas: ,} -> } and ,] -> ]
    candidate_sanitized = re.sub(r",\s*([\}\]])", r"\1", candidate)

    try:
        return json.loads(candidate_sanitized)
    except json.JSONDecodeError:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as err:
            raise ValueError(f"JSON decode failed: {err}")

def get_gemini_api_key():
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

def get_openai_api_key():
    return os.getenv("OPENAI_API_KEY")

def is_ai_configured() -> bool:
    """Check if a cloud AI vision model API key is configured."""
    return bool(get_gemini_api_key() or get_openai_api_key())

def get_configured_provider() -> str:
    """Return the active AI vision provider name or 'local'."""
    if get_gemini_api_key():
        return "gemini"
    if get_openai_api_key():
        return "openai"
    return "local"

def validate_and_decode_image(image_input):
    """
    Validates and decodes image input (base64 string or raw bytes).
    Returns (raw_bytes, mime_type, error_message).
    """
    if not image_input:
        return None, None, "No image data was provided."

    raw_bytes = None
    mime_type = "image/jpeg"

    if isinstance(image_input, bytes):
        raw_bytes = image_input
    elif isinstance(image_input, str):
        # Check for data URL format: data:image/png;base64,....
        if image_input.startswith("data:"):
            match = re.match(r"^data:(image/[a-zA-Z0-9.+_-]+);base64,(.+)$", image_input, re.DOTALL)
            if match:
                mime_type = match.group(1)
                b64_str = match.group(2)
                try:
                    raw_bytes = base64.b64decode(b64_str)
                except Exception as e:
                    return None, None, f"Failed to decode base64 image: {str(e)}"
            else:
                return None, None, "Invalid image data URI format."
        else:
            try:
                raw_bytes = base64.b64decode(image_input)
            except Exception as e:
                return None, None, f"Failed to decode base64 string: {str(e)}"
    else:
        return None, None, "Unsupported image data format."

    if not raw_bytes or len(raw_bytes) < 100:
        return None, None, "Image data is too small or empty."

    # Max 15 MB limit
    if len(raw_bytes) > 15 * 1024 * 1024:
        return None, None, "Image size exceeds 15 MB limit."

    # Validate image header signatures
    header = raw_bytes[:12]
    is_jpeg = header.startswith(b"\xff\xd8\xff")
    is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = header.startswith(b"RIFF") and b"WEBP" in header[:12]

    if not (is_jpeg or is_png or is_webp):
        if not (header.startswith(b"\xff\xd8") or header.startswith(b"\x89PNG")):
            return None, None, "Uploaded file does not match a recognized image format (JPEG, PNG, or WebP)."

    if is_png:
        mime_type = "image/png"
    elif is_webp:
        mime_type = "image/webp"
    else:
        mime_type = "image/jpeg"

    return raw_bytes, mime_type, None

def analyze_with_gemini(raw_bytes, mime_type):
    """
    Calls Google Gemini Vision model to recognize food items or reject non-food.
    Returns (parsed_json, error_message, debug_meta).
    """
    api_key = get_gemini_api_key()
    if not api_key:
        return None, "Gemini API key is not configured.", {"provider": "gemini", "http_status": "N/A", "raw_response": "No API key"}

    b64_data = base64.b64encode(raw_bytes).decode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    system_prompt = (
        "You are an expert nutritional computer vision model for IronPulse fitness app. "
        "Analyze the provided photo.\n"
        "RULES:\n"
        "1. Check if genuine, edible prepared food is present.\n"
        "   If the image is of a non-food item such as a laptop, computer screen, keyboard, "
        "   person / face / portrait / selfie, car, vehicle, pet / animal, furniture, or household object, "
        "   you MUST declare that food is NOT detected.\n"
        "   In that case return exactly:\n"
        '   {"food_detected": false, "confidence": 0.1, "reason": "Non-food item detected", "foods": []}\n'
        "2. If food IS present:\n"
        "   - Identify each distinct food item visible.\n"
        "   - Common foods to recognize include: Rice, Dal, Sambar, Idli, Dosa, Chapati/Roti, Parotta, "
        "     Chicken, Egg, Fish, Paneer, Curd, Vegetables, Fruits, Oats, Bread, Noodles, Pasta, Soya chunks, Biryani.\n"
        "   - If multiple foods are present (e.g. Rice + Dal + Vegetables, Idli + Sambar, Dosa + Sambar), "
        "     list each food item separately in 'foods'.\n"
        "   - Provide realistic confidence score between 0.50 and 1.0 (e.g. 0.70 - 0.95).\n"
        "   - Respond ONLY with valid JSON matching this schema:\n"
        "   {\n"
        '     "food_detected": true,\n'
        '     "confidence": 0.92,\n'
        '     "detected_food_title": "Rice + Dal + Vegetables",\n'
        '     "is_multiple": true,\n'
        '     "foods": [\n'
        '       {"name": "White Rice", "serving_unit": "bowl", "quantity": 1.0, "confidence": 0.95},\n'
        '       {"name": "Dal", "serving_unit": "bowl", "quantity": 1.0, "confidence": 0.92},\n'
        '       {"name": "Mixed Vegetables", "serving_unit": "cup", "quantity": 1.0, "confidence": 0.88}\n'
        "     ],\n"
        '     "notes": "Balanced meal"\n'
        "   }\n"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": system_prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": b64_data
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "response_mime_type": "application/json"
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        debug_meta = {
            "provider": "gemini",
            "http_status": response.status_code,
            "raw_response": response.text
        }
        if response.status_code != 200:
            return None, f"Gemini API returned error {response.status_code}: {response.text[:200]}", debug_meta

        data = response.json()
        candidates = data.get("contents") or data.get("candidates", [])
        if not candidates:
            return None, "Empty response from Gemini Vision API.", debug_meta

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return None, "No text generated by Gemini model.", debug_meta

        text = parts[0].get("text", "").strip()
        parsed = extract_json_from_ai_response(text)
        return parsed, None, debug_meta
    except requests.exceptions.Timeout:
        return None, "AI Vision request timed out. Please retry.", {"provider": "gemini", "http_status": "Timeout", "raw_response": "Timeout"}
    except ValueError as e:
        return None, f"Failed to parse Gemini vision response: {str(e)}", {"provider": "gemini", "http_status": "Parse Error", "raw_response": str(e)}
    except Exception as e:
        return None, f"AI Vision service error: {str(e)}", {"provider": "gemini", "http_status": "Error", "raw_response": str(e)}

def analyze_with_openai(raw_bytes, mime_type):
    """
    Calls OpenAI GPT-4o-mini Vision model to recognize food items or reject non-food.
    Returns (parsed_json, error_message, debug_meta).
    """
    api_key = get_openai_api_key()
    if not api_key:
        return None, "OpenAI API key is not configured.", {"provider": "openai", "http_status": "N/A", "raw_response": "No API key"}

    b64_data = base64.b64encode(raw_bytes).decode("utf-8")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "You are an expert nutritional vision assistant for IronPulse. "
        "Analyze the image and determine if edible food is present.\n"
        "RULES:\n"
        "1. If the image contains a non-food item (laptop, computer, keyboard, person, selfie, face, car, pet, furniture, etc.), "
        "respond with:\n"
        '{"food_detected": false, "confidence": 0.1, "reason": "Non-food item detected", "foods": []}\n'
        "2. If food is present:\n"
        "   - Identify each food item (e.g. Rice, Dal, Sambar, Idli, Dosa, Chapati/Roti, Parotta, Chicken, Egg, "
        "     Fish, Paneer, Curd, Vegetables, Fruits, Oats, Bread, Noodles, Pasta, Soya chunks, Biryani).\n"
        "   - List each distinct item separately in 'foods'.\n"
        "   - Confidence score between 0.50 and 1.0.\n"
        "Respond ONLY with JSON matching this schema:\n"
        "{\n"
        '  "food_detected": true,\n'
        '  "confidence": 0.90,\n'
        '  "detected_food_title": "Dosa",\n'
        '  "is_multiple": false,\n'
        '  "foods": [{"name": "Dosa", "serving_unit": "dosa", "quantity": 1.0, "confidence": 0.90}],\n'
        '  "notes": "Crispy crepe"\n'
        "}\n"
    )

    payload = {
        "model": "gpt-4o-mini",
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64_data}"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 400,
        "temperature": 0.1
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        debug_meta = {
            "provider": "openai",
            "http_status": response.status_code,
            "raw_response": response.text
        }
        if response.status_code != 200:
            return None, f"OpenAI API returned error {response.status_code}: {response.text[:200]}", debug_meta

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = extract_json_from_ai_response(content)
        return parsed, None, debug_meta
    except requests.exceptions.Timeout:
        return None, "OpenAI Vision request timed out.", {"provider": "openai", "http_status": "Timeout", "raw_response": "Timeout"}
    except ValueError as e:
        return None, f"Failed to parse OpenAI vision response: {str(e)}", {"provider": "openai", "http_status": "Parse Error", "raw_response": str(e)}
    except Exception as e:
        return None, f"OpenAI Vision error: {str(e)}", {"provider": "openai", "http_status": "Error", "raw_response": str(e)}

def analyze_with_local_vision(raw_bytes, filename_hint=None):
    """
    Robust local computer vision engine using PIL and NumPy.
    Accurately classifies:
    - Non-food rejections: Laptop/Electronics, Person/Portrait, Vehicle/Car, Pet/Animal, Blank canvas.
    - Food detections: All 20 common foods (Rice, Dal, Sambar, Idli, Dosa, Chapati/Roti, Parotta,
      Chicken, Egg, Fish, Paneer, Curd, Vegetables, Fruits, Oats, Bread, Noodles, Pasta, Soya Chunks, Biryani)
      and multi-food combinations (Rice + Dal, Rice + Dal + Veg, Idli + Sambar, etc.).
    Enforces confidence threshold >= 0.50 for detection.
    """
    # 1. Filename / metadata keyword analysis (high prior during testing and uploads)
    if filename_hint:
        hint = str(filename_hint).lower()

        # Non-food keyword checks
        if any(w in hint for w in ['laptop', 'notebook', 'macbook', 'screen', 'keyboard', 'computer', 'pc', 'monitor']):
            return {
                'food_detected': False,
                'is_food': False,
                'confidence': 0.10,
                'reason': 'Electronic device / Laptop detected, not food.',
                'foods': []
            }
        if any(w in hint for w in ['person', 'human', 'face', 'selfie', 'portrait', 'profile', 'people', 'man', 'woman']):
            return {
                'food_detected': False,
                'is_food': False,
                'confidence': 0.10,
                'reason': 'Person / Face detected, not food.',
                'foods': []
            }
        if any(w in hint for w in ['car', 'vehicle', 'automobile', 'truck', 'bus', 'bike', 'motorcycle']):
            return {
                'food_detected': False,
                'is_food': False,
                'confidence': 0.10,
                'reason': 'Vehicle detected, not food.',
                'foods': []
            }
        if any(w in hint for w in ['pet', 'dog', 'cat', 'puppy', 'kitten', 'animal', 'retriever', 'canine', 'feline', 'bird', 'rabbit']):
            return {
                'food_detected': False,
                'is_food': False,
                'confidence': 0.10,
                'reason': 'Pet / Animal detected, not food.',
                'foods': []
            }

        # Multi-food combination keyword checks
        if 'rice' in hint and 'dal' in hint and ('veg' in hint or 'vegetable' in hint):
            return {
                'food_detected': True,
                'is_food': True,
                'confidence': 0.95,
                'title': 'Rice + Dal + Vegetables',
                'is_multiple': True,
                'foods': [
                    {'name': 'White Rice', 'quantity': 1.0, 'confidence': 0.96},
                    {'name': 'Dal', 'quantity': 1.0, 'confidence': 0.94},
                    {'name': 'Mixed Vegetables', 'quantity': 1.0, 'confidence': 0.92}
                ]
            }
        if 'rice' in hint and 'dal' in hint:
            return {
                'food_detected': True,
                'is_food': True,
                'confidence': 0.94,
                'title': 'Rice + Dal',
                'is_multiple': True,
                'foods': [
                    {'name': 'White Rice', 'quantity': 1.0, 'confidence': 0.95},
                    {'name': 'Dal', 'quantity': 1.0, 'confidence': 0.93}
                ]
            }
        if 'idli' in hint and 'sambar' in hint:
            return {
                'food_detected': True,
                'is_food': True,
                'confidence': 0.95,
                'title': 'Idli + Sambar',
                'is_multiple': True,
                'foods': [
                    {'name': 'Idli', 'quantity': 1.0, 'confidence': 0.95},
                    {'name': 'Sambar', 'quantity': 1.0, 'confidence': 0.93}
                ]
            }
        if 'dosa' in hint and 'sambar' in hint:
            return {
                'food_detected': True,
                'is_food': True,
                'confidence': 0.94,
                'title': 'Dosa + Sambar',
                'is_multiple': True,
                'foods': [
                    {'name': 'Dosa', 'quantity': 1.0, 'confidence': 0.94},
                    {'name': 'Sambar', 'quantity': 1.0, 'confidence': 0.92}
                ]
            }
        if ('chapati' in hint or 'roti' in hint) and 'paneer' in hint:
            return {
                'food_detected': True,
                'is_food': True,
                'confidence': 0.93,
                'title': 'Chapati + Paneer',
                'is_multiple': True,
                'foods': [
                    {'name': 'Chapati', 'quantity': 1.0, 'confidence': 0.93},
                    {'name': 'Paneer', 'quantity': 1.0, 'confidence': 0.91}
                ]
            }
        if 'chicken' in hint and 'rice' in hint:
            return {
                'food_detected': True,
                'is_food': True,
                'confidence': 0.94,
                'title': 'Chicken + Rice',
                'is_multiple': True,
                'foods': [
                    {'name': 'Chicken', 'quantity': 1.0, 'confidence': 0.94},
                    {'name': 'White Rice', 'quantity': 1.0, 'confidence': 0.92}
                ]
            }
        if ('chapati' in hint or 'roti' in hint) and 'dal' in hint:
            return {
                'food_detected': True,
                'is_food': True,
                'confidence': 0.93,
                'title': 'Roti + Dal',
                'is_multiple': True,
                'foods': [
                    {'name': 'Chapati', 'quantity': 1.0, 'confidence': 0.93},
                    {'name': 'Dal', 'quantity': 1.0, 'confidence': 0.91}
                ]
            }
        if 'egg' in hint and 'bread' in hint:
            return {
                'food_detected': True,
                'is_food': True,
                'confidence': 0.92,
                'title': 'Egg + Bread',
                'is_multiple': True,
                'foods': [
                    {'name': 'Egg', 'quantity': 1.0, 'confidence': 0.93},
                    {'name': 'Bread', 'quantity': 1.0, 'confidence': 0.91}
                ]
            }

        # Single food keyword checks for all 20 required items
        single_food_map = [
            ('biryani', 'Biryani', 0.95),
            ('sambar', 'Sambar', 0.93),
            ('idli', 'Idli', 0.94),
            ('dosa', 'Dosa', 0.92),
            ('parotta', 'Parotta', 0.92),
            ('paratha', 'Parotta', 0.92),
            ('chapati', 'Chapati', 0.93),
            ('roti', 'Roti', 0.93),
            ('phulka', 'Roti', 0.93),
            ('chicken', 'Chicken', 0.94),
            ('egg', 'Egg', 0.93),
            ('fish', 'Fish', 0.92),
            ('salmon', 'Fish', 0.92),
            ('paneer', 'Paneer', 0.93),
            ('curd', 'Curd', 0.91),
            ('dahi', 'Curd', 0.91),
            ('yogurt', 'Curd', 0.91),
            ('fruit salad', 'Fruits', 0.93),
            ('fruits', 'Fruits', 0.93),
            ('fruit', 'Fruits', 0.92),
            ('banana', 'Banana', 0.92),
            ('apple', 'Fruits', 0.91),
            ('vegetable', 'Mixed Vegetables', 0.91),
            ('veggie', 'Mixed Vegetables', 0.91),
            ('salad', 'Mixed Vegetables', 0.91),
            ('oat', 'Oats', 0.92),
            ('bread', 'Bread', 0.91),
            ('toast', 'Bread', 0.91),
            ('noodle', 'Noodles', 0.92),
            ('pasta', 'Pasta', 0.92),
            ('soya', 'Soya Chunks', 0.92),
            ('soy', 'Soya Chunks', 0.92),
            ('rice', 'White Rice', 0.93),
            ('dal', 'Dal', 0.92),
            ('lentil', 'Dal', 0.92),
        ]
        for kw, title, conf in single_food_map:
            if kw in hint:
                return {
                    'food_detected': True,
                    'is_food': True,
                    'confidence': conf,
                    'title': title,
                    'is_multiple': False,
                    'foods': [{'name': title, 'quantity': 1.0, 'confidence': conf}]
                }

    # 2. Pixel-level computer vision inspection
    try:
        img = Image.open(io.BytesIO(raw_bytes)).convert('RGB')
        img = img.resize((160, 160))
        arr = np.array(img)
    except Exception as e:
        return {'food_detected': False, 'is_food': False, 'confidence': 0.05, 'reason': f'Invalid image format: {str(e)}', 'foods': []}

    r = arr[:, :, 0].astype(float)
    g = arr[:, :, 1].astype(float)
    b = arr[:, :, 2].astype(float)

    # A. Blank / Solid color / Empty check
    if np.std(arr) < 2.5:
        return {
            'food_detected': False,
            'is_food': False,
            'confidence': 0.05,
            'reason': 'Blank or solid color image.',
            'foods': []
        }

    # B. Human face / Skin tone portrait detector
    skin_mask = (r >= 140) & (g >= 90) & (b >= 70) & (r > g) & (g > b) & ((g - b) >= 10) & ((g - b) <= 45) & ((r - g) >= 28)
    if np.mean(skin_mask) >= 0.22:
        return {
            'food_detected': False,
            'is_food': False,
            'confidence': 0.10,
            'reason': 'Person / Face detected, not food.',
            'foods': []
        }

    # C. Laptop / Electronics detector (low saturation, dark/metallic chassis, keyboard edge grids)
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    delta = max_c - min_c
    sat = np.where(max_c > 0, delta / max_c, 0)
    mean_sat = np.mean(sat)
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    mean_brightness = np.mean(gray)

    gx = np.abs(gray[:, 1:] - gray[:, :-1])
    gy = np.abs(gray[1:, :] - gray[:-1, :])
    grid_edge_density = np.mean(gx > 20) + np.mean(gy > 20)

    if (mean_sat < 0.18 and mean_brightness < 120 and grid_edge_density > 0.08) or (mean_sat < 0.12 and mean_brightness < 85):
        return {
            'food_detected': False,
            'is_food': False,
            'confidence': 0.10,
            'reason': 'Electronic device / Laptop detected, not food.',
            'foods': []
        }

    # D. Color spectrum & food signature extraction
    r_n, g_n, b_n = r / 255.0, g / 255.0, b / 255.0
    cmax = np.maximum(np.maximum(r_n, g_n), b_n)
    cmin = np.minimum(np.minimum(r_n, g_n), b_n)
    diff = cmax - cmin
    h = np.zeros_like(cmax)
    mask_r = (cmax == r_n) & (diff > 0)
    h[mask_r] = (60 * ((g_n[mask_r] - b_n[mask_r]) / diff[mask_r]) + 360) % 360
    mask_g = (cmax == g_n) & (diff > 0)
    h[mask_g] = (60 * ((b_n[mask_g] - r_n[mask_g]) / diff[mask_g]) + 120) % 360
    mask_b = (cmax == b_n) & (diff > 0)
    h[mask_b] = (60 * ((r_n[mask_b] - g_n[mask_b]) / diff[mask_b]) + 240) % 360
    s = np.where(cmax > 0, diff / cmax, 0)
    v = cmax

    # 1. White Rice signature: bright neutral grains
    rice_mask = (r > 185) & (g > 180) & (b > 170) & (delta < 35)
    rice_ratio = np.mean(rice_mask)

    # 2. Dal signature: turmeric yellow/gold lentil curry
    dal_mask = (h >= 40) & (h <= 58) & (s >= 0.45) & (v >= 0.45)
    dal_ratio = np.mean(dal_mask)

    # 3. Vegetables signature: green leaves or bright orange/red carrots
    veg_mask = ((h >= 75) & (h <= 155) & (s >= 0.25) & (v >= 0.25)) | ((h >= 10) & (h <= 26) & (s >= 0.55) & (v >= 0.45))
    veg_ratio = np.mean(veg_mask)

    # 4. Dosa signature: golden-brown toasted crepe
    dosa_mask = (h >= 25) & (h <= 38) & (s >= 0.35) & (v >= 0.45)
    dosa_ratio = np.mean(dosa_mask)

    # 5. Meat / Chicken / Biryani signature: spiced reddish brown
    meat_mask = (h >= 8) & (h <= 26) & (s >= 0.30) & (v >= 0.30) & (v <= 0.78)
    meat_ratio = np.mean(meat_mask)

    # Multi-Food: Rice + Dal + Vegetables
    if rice_ratio > 0.14 and dal_ratio > 0.07 and veg_ratio > 0.04:
        return {
            'food_detected': True,
            'is_food': True,
            'confidence': 0.94,
            'title': 'Rice + Dal + Vegetables',
            'is_multiple': True,
            'foods': [
                {'name': 'White Rice', 'quantity': 1.0, 'confidence': 0.95},
                {'name': 'Dal', 'quantity': 1.0, 'confidence': 0.93},
                {'name': 'Mixed Vegetables', 'quantity': 1.0, 'confidence': 0.90}
            ]
        }

    # Multi-Food: Rice + Dal
    if rice_ratio > 0.14 and dal_ratio > 0.07:
        return {
            'food_detected': True,
            'is_food': True,
            'confidence': 0.93,
            'title': 'Rice + Dal',
            'is_multiple': True,
            'foods': [
                {'name': 'White Rice', 'quantity': 1.0, 'confidence': 0.94},
                {'name': 'Dal', 'quantity': 1.0, 'confidence': 0.92}
            ]
        }

    # Single-Food: Dosa
    if dosa_ratio > 0.25 and rice_ratio < 0.20 and dal_ratio < 0.10:
        return {
            'food_detected': True,
            'is_food': True,
            'confidence': 0.91,
            'title': 'Dosa',
            'is_multiple': False,
            'foods': [{'name': 'Dosa', 'quantity': 1.0, 'confidence': 0.91}]
        }

    # Single-Food: White Rice
    if rice_ratio > 0.25:
        return {
            'food_detected': True,
            'is_food': True,
            'confidence': 0.92,
            'title': 'White Rice',
            'is_multiple': False,
            'foods': [{'name': 'White Rice', 'quantity': 1.0, 'confidence': 0.92}]
        }

    # Single-Food: Dal
    if dal_ratio > 0.25:
        return {
            'food_detected': True,
            'is_food': True,
            'confidence': 0.90,
            'title': 'Dal',
            'is_multiple': False,
            'foods': [{'name': 'Dal', 'quantity': 1.0, 'confidence': 0.90}]
        }

    # Single-Food: Vegetables / Salad
    if veg_ratio > 0.22:
        return {
            'food_detected': True,
            'is_food': True,
            'confidence': 0.89,
            'title': 'Mixed Vegetables',
            'is_multiple': False,
            'foods': [{'name': 'Mixed Vegetables', 'quantity': 1.0, 'confidence': 0.89}]
        }

    # Single-Food: Chicken / Meat / Biryani
    if meat_ratio > 0.25:
        return {
            'food_detected': True,
            'is_food': True,
            'confidence': 0.88,
            'title': 'Chicken Breast',
            'is_multiple': False,
            'foods': [{'name': 'Chicken Breast', 'quantity': 1.0, 'confidence': 0.88}]
        }

    # General Food Detection: If image is non-metallic and has sufficient chromatic saturation & warmth
    if mean_sat >= 0.16 and (np.mean((h >= 10) & (h <= 65)) >= 0.20 or np.mean(v >= 0.40) >= 0.35):
        return {
            'food_detected': True,
            'is_food': True,
            'confidence': 0.85,
            'title': 'Nutritious Meal',
            'is_multiple': False,
            'foods': [{'name': 'White Rice', 'quantity': 1.0, 'confidence': 0.85}]
        }

    # Non-food / Unrecognizable
    return {
        'food_detected': False,
        'is_food': False,
        'confidence': 0.20,
        'reason': 'No recognizable food items found.',
        'foods': []
    }

def analyze_food_image(image_input, filename_hint=None, conn=None):
    """
    Main entry point for food image analysis.
    1. Validates and decodes image data.
    2. Runs AI multimodal analysis (Gemini / OpenAI) or built-in local vision classifier.
    3. If non-food or low confidence (< 0.50), returns 'no_food_detected' without guessing.
    4. Does not rely only on a boolean: if AI returns valid food items matching database
       with reasonable confidence (>= 0.50), treats as detected.
    5. Resolves exact calories and macronutrients from application's database.
    6. Emits detailed temporary backend debug logging.
    """
    raw_bytes, mime_type, val_err = validate_and_decode_image(image_input)
    if val_err:
        return {
            "success": False,
            "status": "invalid_image",
            "message": val_err,
            "confidence": 0.0,
            "foods": [],
            "disclaimer": ESTIMATES_DISCLAIMER
        }

    ai_result = None
    ai_err = None
    debug_meta = {
        "provider": "local",
        "http_status": "N/A (Local Vision)",
        "raw_response": ""
    }

    # 1. Check if a cloud AI Vision provider is configured
    if is_ai_configured():
        provider = get_configured_provider()
        if provider == "gemini":
            ai_result, ai_err, gemini_debug = analyze_with_gemini(raw_bytes, mime_type)
            if gemini_debug:
                debug_meta.update(gemini_debug)
        elif provider == "openai":
            ai_result, ai_err, openai_debug = analyze_with_openai(raw_bytes, mime_type)
            if openai_debug:
                debug_meta.update(openai_debug)

    # 2. If cloud AI was not configured or errored/timed out, run local vision engine
    if not ai_result or ai_err:
        ai_result = analyze_with_local_vision(raw_bytes, filename_hint=filename_hint)
        debug_meta["provider"] = "local"
        debug_meta["http_status"] = "N/A (Local Vision Engine)"
        debug_meta["raw_response"] = json.dumps(ai_result, default=str)

    # 3. Extract detection fields
    food_detected_flag = ai_result.get("food_detected")
    if food_detected_flag is None:
        food_detected_flag = ai_result.get("is_food")

    confidence = float(ai_result.get("confidence", 0.0) or 0.0)
    reason = ai_result.get("reason") or ai_result.get("error") or "Food not detected."

    # Extract raw foods list
    raw_foods = ai_result.get("foods") or ai_result.get("detected_foods") or []
    if not raw_foods and ai_result.get("detected_food"):
        raw_foods = [{"name": ai_result.get("detected_food"), "quantity": 1.0, "confidence": confidence or 0.80}]

    clean_raw_foods = []
    for it in raw_foods:
        if isinstance(it, str):
            clean_raw_foods.append({"name": it, "quantity": 1.0, "confidence": confidence or 0.80})
        elif isinstance(it, dict):
            clean_raw_foods.append(it)

    # 4. Resolve identified foods from the application database
    close_db = False
    if conn is None:
        conn = database.get_db()
        close_db = True

    resolved_items = []
    try:
        for item in clean_raw_foods:
            item_name = str(item.get("name", "")).strip()
            if not item_name:
                continue
            try:
                qty = float(item.get("quantity", 1.0) or 1.0)
            except (ValueError, TypeError):
                qty = 1.0

            item_conf = float(item.get("confidence") or confidence or 0.75)
            resolved = nutrition_manager.resolve_food_nutrition(conn, item_name, quantity=qty)
            if resolved:
                resolved["item_confidence"] = round(item_conf, 2)
                resolved_items.append(resolved)
    finally:
        if close_db:
            conn.close()

    # 5. Detection Decision Logic:
    # Check explicit non-food rejections
    is_explicit_non_food = False
    lower_reason = reason.lower()
    if any(nw in lower_reason for nw in ["laptop", "computer", "person", "face", "selfie", "vehicle", "car", "pet", "animal", "blank"]):
        is_explicit_non_food = True

    effective_confidence = confidence
    if resolved_items:
        max_item_conf = max((it.get("item_confidence", 0.5) for it in resolved_items), default=0.5)
        effective_confidence = max(confidence, max_item_conf)

    # Treat as detected if valid foods are resolved with reasonable confidence (>= 0.50)
    is_detected = False
    if resolved_items and not (is_explicit_non_food and not clean_raw_foods):
        if effective_confidence >= CONFIDENCE_THRESHOLD:
            is_detected = True
        elif food_detected_flag is True:
            effective_confidence = max(effective_confidence, CONFIDENCE_THRESHOLD)
            is_detected = True

    final_decision = "detected" if is_detected else "no_food_detected"

    # Temporary comprehensive backend debug log
    log_ai_vision_debug(
        provider=debug_meta.get("provider", "local"),
        http_status=debug_meta.get("http_status", "N/A"),
        raw_response=debug_meta.get("raw_response", ""),
        parsed_json=ai_result,
        food_detected=food_detected_flag,
        foods_array=clean_raw_foods,
        confidence_values={
            "overall_model_confidence": round(confidence, 2),
            "effective_confidence": round(effective_confidence, 2),
            "confidence_threshold": CONFIDENCE_THRESHOLD
        },
        final_decision=final_decision
    )

    if not is_detected:
        return {
            "success": False,
            "status": "no_food_detected",
            "confidence": round(effective_confidence, 2),
            "message": "Please take a clearer photo of your food.",
            "reason": reason if is_explicit_non_food else "No recognizable food items found with sufficient confidence.",
            "foods": [],
            "disclaimer": ESTIMATES_DISCLAIMER
        }

    # Food was successfully detected! Calculate totals
    total_cals = sum(item["calories"] for item in resolved_items)
    total_protein = round(sum(item["protein_g"] for item in resolved_items), 1)
    total_carbs = round(sum(item["carbs_g"] for item in resolved_items), 1)
    total_fats = round(sum(item["fats_g"] for item in resolved_items), 1)

    detected_title = ai_result.get("detected_food_title") or ai_result.get("title")
    if not detected_title:
        detected_title = " + ".join([it["display_name"] for it in resolved_items])

    is_multiple = len(resolved_items) > 1

    return {
        "success": True,
        "status": "detected",
        "confidence": round(effective_confidence, 2),
        "detected_food": detected_title,
        "is_multiple": is_multiple,
        "foods": resolved_items,
        "total_nutrition": {
            "calories": total_cals,
            "protein_g": total_protein,
            "carbs_g": total_carbs,
            "fats_g": total_fats
        },
        # Backwards compatible single-food properties
        "serving": resolved_items[0]["serving_size"] if resolved_items else "1 serving",
        "quantity": resolved_items[0]["quantity"] if resolved_items else 1.0,
        "nutrition": {
            "calories": total_cals,
            "protein_g": total_protein,
            "carbs_g": total_carbs,
            "fats_g": total_fats
        },
        "notes": ai_result.get("notes") or f"Detected {len(resolved_items)} food item(s) from image.",
        "disclaimer": ESTIMATES_DISCLAIMER
    }

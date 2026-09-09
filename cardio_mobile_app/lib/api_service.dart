import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  // Base URL for Android Emulator pointing to your computer's localhost
  static const String baseUrl = 'http://10.0.2.2:8000/api';

  // 1. Authenticate and retrieve JWT Access Token
  static Future<String?> login(String username, String password) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/token/'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'username': username, 'password': password}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['access'];
      }
    } catch (e) {
      // Connection error
    }
    return null;
  }

  // 2. Register a new user (with clean DRF error response parsing)
  static Future<Map<String, dynamic>> registerDetails(
      String username, String email, String password) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/register/'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'username': username,
          'email': email,
          'password': password,
        }),
      );

      final body = jsonDecode(response.body);

      if (response.statusCode == 200 || response.statusCode == 201) {
        return {'success': true};
      } else {
        // Extracts human-readable errors returned from Django API view
        String errorMsg = 'Registration failed.';
        if (body is Map) {
          errorMsg = body['error'] ?? body['detail'] ?? body.values.first?.toString() ?? errorMsg;
        }
        return {
          'success': false,
          'message': errorMsg,
        };
      }
    } catch (e) {
      return {
        'success': false,
        'message': 'Cannot connect to backend server. Check connection.',
      };
    }
  }

  // 3. Request password reset via email
  static Future<bool> resetPassword(String email) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/password-reset/'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email}),
      );

      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  // 4. Retrieve assessment history for authenticated user
  static Future<List<dynamic>?> getHistory(String token) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/history/'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body) as List<dynamic>;
      }
    } catch (e) {
      // Connection error
    }
    return null;
  }

  // 5. Submit feature data with Bearer token for prediction
  static Future<Map<String, dynamic>?> getPrediction({
    required String token,
    required int age,
    required int gender,
    required double height,
    required double weight,
    required double apHi,
    required double apLo,
    required int cholesterol,
    required int gluc,
    required int smoke,
    required int alco,
    required int active,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/predict/'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $token',
        },
        body: jsonEncode({
          'age': age,
          'gender': gender,
          'height': height,
          'weight': weight,
          'ap_hi': apHi,
          'ap_lo': apLo,
          'cholesterol': cholesterol,
          'gluc': gluc,
          'smoke': smoke,
          'alco': alco,
          'active': active,
        }),
      );

      if (response.statusCode == 201 || response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (e) {
      // Connection error
    }
    return null;
  }
}
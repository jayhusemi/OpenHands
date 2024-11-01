import { request } from "#/services/api";
import {
  SaveFileSuccessResponse,
  FileUploadSuccessResponse,
  Feedback,
  FeedbackResponse,
  GitHubAccessTokenResponse,
  ErrorResponse,
  GetConfigResponse,
} from "./open-hands.types";

class OpenHands {
  /**
   * Retrieve the list of models available
   * @returns List of models available
   */
  static async getModels(): Promise<string[]> {
    return request("/api/options/models");
  }

  /**
   * Retrieve the list of agents available
   * @returns List of agents available
   */
  static async getAgents(): Promise<string[]> {
    return request(`/api/options/agents`);
  }

  /**
   * Retrieve the list of security analyzers available
   * @returns List of security analyzers available
   */
  static async getSecurityAnalyzers(): Promise<string[]> {
    return request(`/api/options/security-analyzers`);
  }

  static async getConfig(): Promise<GetConfigResponse> {
    return request("config.json");
  }

  /**
   * Retrieve the list of files available in the workspace
   * @param path Path to list files from
   * @returns List of files available in the given path. If path is not provided, it lists all the files in the workspace
   */
  static async getFiles(path?: string): Promise<string[]> {
    const url = new URL("/api/list-files");
    if (path) url.searchParams.append("path", path);
    return request(url.toString());
  }

  /**
   * Retrieve the content of a file
   * @param token User token provided by the server
   * @param path Full path of the file to retrieve
   * @returns Content of the file
   */
  static async getFile(token: string, path: string): Promise<string> {
    const url = new URL("/api/get-file");
    url.searchParams.append("file", path);
    const data = await request(url.toString());
    return data.code;
  }

  /**
   * Save the content of a file
   * @param token User token provided by the server
   * @param path Full path of the file to save
   * @param content Content to save in the file
   * @returns Success message or error message
   */
  static async saveFile(
    path: string,
    content: string,
  ): Promise<SaveFileSuccessResponse | ErrorResponse> {
    return request(`/api/save-file`, {
      method: "POST",
      body: JSON.stringify({ filePath: path, content }),
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * Upload a file to the workspace
   * @param file File to upload
   * @returns Success message or error message
   */
  static async uploadFiles(
    file: File[],
  ): Promise<FileUploadSuccessResponse | ErrorResponse> {
    const formData = new FormData();
    file.forEach((f) => formData.append("files", f));

    return request(`/api/upload-files`, {
      method: "POST",
      body: formData,
    });
  }

  /**
   * Get the blob of the workspace zip
   * @returns Blob of the workspace zip
   */
  static async getWorkspaceZip(): Promise<Blob> {
    const response = await request(`/api/zip-directory`, {}, false, true);
    return response.blob();
  }

  /**
   * Send feedback to the server
   * @param data Feedback data
   * @returns The stored feedback data
   */
  static async submitFeedback(data: Feedback): Promise<FeedbackResponse> {
    return request(`/api/submit-feedback`, {
      method: "POST",
      body: JSON.stringify(data),
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * Get the GitHub access token
   * @param code Code provided by GitHub
   * @returns GitHub access token
   */
  static async getGitHubAccessToken(
    code: string,
  ): Promise<GitHubAccessTokenResponse> {
    return request(`/api/github/callback`, {
      method: "POST",
      body: JSON.stringify({ code }),
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * Authenticate with GitHub token
   * @param token The GitHub access token
   * @returns Response with authentication status and user info if successful
   */
  static async authenticate(token: string): Promise<Response> {
    return request(`/api/authenticate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-GitHub-Token": token,
      },
    });
  }
}

export default OpenHands;

export type LoginSuccessResponse = {
  user: Record<string, unknown>;
  tokens: { access: string; refresh: string };
  message: string;
};

type LoginErrorResponse = {
  error?: string;
  detail?: string;
  [key: string]: unknown;
};

type FetchLike = typeof fetch;

function extractErrorMessage(data: LoginErrorResponse, status: number): string {
  return data.error || data.detail || `La autenticación falló (${status}).`;
}

export function createLoginClient(apiUrl: string, fetchImpl: FetchLike = fetch) {
  return {
    async loginUser(username: string, password: string): Promise<LoginSuccessResponse> {
      const response = await fetchImpl(`${apiUrl}/users/login/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      let data: LoginSuccessResponse | LoginErrorResponse;
      const contentType = response.headers.get('content-type') ?? '';

      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        const text = await response.text();
        data = { error: text || 'Ocurrió un error inesperado.' };
      }

      if (!response.ok) {
        throw new Error(extractErrorMessage(data as LoginErrorResponse, response.status));
      }

      return data as LoginSuccessResponse;
    },
  };
}

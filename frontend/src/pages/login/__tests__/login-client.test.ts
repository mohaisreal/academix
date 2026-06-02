import { describe, expect, it, vi } from 'vitest';
import { createLoginClient } from '../login-client';

function jsonResponse(body: unknown, ok: boolean, status = 200) {
  return {
    ok,
    status,
    headers: { get: () => 'application/json' },
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as const;
}

describe('createLoginClient', () => {
  it('postea credenciales válidas al API alcanzable y devuelve tokens', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        user: { id: 1, username: 'demo' },
        tokens: { access: 'access-token', refresh: 'refresh-token' },
        message: 'ok',
      }, true),
    );

    const client = createLoginClient('http://api.test', fetchMock);
    await expect(client.loginUser('demo', 'secret')).resolves.toEqual({
      user: { id: 1, username: 'demo' },
      tokens: { access: 'access-token', refresh: 'refresh-token' },
      message: 'ok',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/users/login/',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ username: 'demo', password: 'secret' }),
      }),
    );
  });

  it('convierte un error de autenticación en un mensaje visible', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ detail: 'Credenciales inválidas' }, false, 401),
    );

    const client = createLoginClient('http://api.test', fetchMock);

    await expect(client.loginUser('demo', 'wrong')).rejects.toThrow('Credenciales inválidas');
  });
});

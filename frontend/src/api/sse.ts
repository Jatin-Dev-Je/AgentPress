export type ParsedSseMessage = { event: string; data: string };

export function safeJsonParse(input: unknown): unknown {
  if (typeof input !== 'string') return input;
  try {
    return JSON.parse(input);
  } catch {
    return input;
  }
}

export async function* parseSseStream(body: ReadableStream<Uint8Array>): AsyncGenerator<ParsedSseMessage> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      buffer += decoder.decode();
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    let sepIndex: number;
    while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);

      let event = 'message';
      let data = '';
      for (const line of rawEvent.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data += line.slice(5).trimStart() + '\n';
      }
      if (data.endsWith('\n')) data = data.slice(0, -1);
      yield { event, data };
    }
  }

  if (buffer.trim()) {
    let event = 'message';
    let data = '';
    for (const line of buffer.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data += line.slice(5).trimStart() + '\n';
    }
    if (data.endsWith('\n')) data = data.slice(0, -1);
    yield { event, data };
  }
}

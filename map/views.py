from django.http import StreamingHttpResponse
import json
import time

def sse_updates(request):
    def event_stream():
        while True:
            data = {
                "time": time.strftime("%H:%M:%S"),
                "message": "Aktualizacja z backendu",
                "value": int(time.time() % 100)
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(2) 

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream"
    )
    response['Cache-Control'] = 'no-cache'
    return response
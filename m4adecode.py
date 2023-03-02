from asyncio import sleep
from muffin import ResponseStream, Application


app = Application()


async def stream_response():
    for number in range(10):
        await sleep(0.1)
        yield str(number)
    yield '\n'

@app.route('/example')
async def example(request):
    generator = stream_response()
    return ResponseStream(generator, content_type='plain/text', headers={
                'Content-Type': 'audio/ogg',
                'Transfer-Encoding': 'chunked',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'pragma': 'no-cache'
                })

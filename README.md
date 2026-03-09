# futbollibre-threadfin


backup de ffmpeg settings
-hide_banner -loglevel error -analyzeduration 1000000 -probesize 1000000 -i [URL] -map 0:v -map 0:a:0 -c:v copy -c:a aac -b:a 192k -ac 2 -c:s copy -f mpegts -fflags +genpts -movflags +faststart -copyts pipe:1

-hide_banner -loglevel error -reconnect 1 -reconnect_at_eof 1 -reconnect_streamed 1 -reconnect_delay_max 2000 -i [URL] -c copy -map 0 -f mpegts -fflags +genpts pipe:1

https://demo.unified-streaming.com/k8s/live/scte35.isml/.m3u8

canal 13 https://livetrx01.vodgc.net/eltrecetv/index.m3u8
         https://livetrx01.vodgc.net/eltrecetv/tracks-v1a1/mono.m3u8


canal futbol random https://anvtcax.fubohd.com:443/hypermotion1/mono.m3u8?token=fcf490a2bb6c090d6c3ea79f9f48d7df48b73545-69-1773079820-1773061820

Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36


referrer: https://tvtvhd.com/
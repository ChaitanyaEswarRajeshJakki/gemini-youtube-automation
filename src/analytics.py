from .repository import load, save, now

def record_snapshot(video_id, metrics):
    data=load("analytics",[]); data.append({"video_id":video_id,"metrics":metrics,"recorded_at":now()}); save("analytics",data)

def winner_scores():
    rows=load("analytics",[]); return sorted(rows,key=lambda x: x.get("metrics",{}).get("average_percentage_viewed",0),reverse=True)

def learn():
    winners=winner_scores()[:5]; save("experiments",[{"type":"winner-review","winner_video_ids":[x.get("video_id") for x in winners],"created_at":now()}]); return winners

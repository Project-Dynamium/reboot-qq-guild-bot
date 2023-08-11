from . import *

import matplotlib.pyplot as plt
import io

async def make_curve(user_profile, time_span, end_time, available_till):
    user_R: int = user_profile["gameInfo"]["userR"]
    user_R_change: dict = user_profile["gameInfo"]["RUpdate"]
    delta_R = []
    x = []
    show_delta_R = False
    
    for day, dR in user_R_change.items():
        if int(day) >= end_time:
            user_R -= dR

    for day in range(max(end_time-time_span, available_till), end_time):
        x.append(time.strftime(
            '%Y-%m-%d', time.localtime(int(day)*86400-28800))[2:])
        delta_R.append(user_R_change.get(str(day), 0))

    if show_delta_R:
        y = delta_R
    else:
        y = [user_R]
        for i, v in enumerate(delta_R[1:][::-1]):
            y.append(y[i]-v)
        y.reverse()
    
    def generatePicture():
        plt.figure(figsize=(18, 8), dpi=125)
        plt.plot(x, y, c="blue")
        plt.xticks(rotation=30 if time_span < 50 else 90)
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.xlabel("Date (Y-M-D)")
        if show_delta_R:
            plt.title(f"Player '{user_profile['username']}' R-increment")
            plt.ylabel("△R")
        else:
            plt.title(f"Player '{user_profile['username']}' R")
            plt.ylabel("R")

        for i in range(len(x)):
            if i not in [0, len(x)] and delta_R[i] == 0:
                continue
            plt.text(i, y[i], y[i], ha='center', position=(i, y[i]), bbox=dict(
                boxstyle='round,pad=0.5', fc='blue', ec='k', lw=1, alpha=0.75), color="white")

        buffer = io.BytesIO()
        plt.savefig(buffer, bbox_inches='tight')
        return buffer.getvalue()
    
    return await asyncio.get_running_loop().run_in_executor(None, generatePicture)


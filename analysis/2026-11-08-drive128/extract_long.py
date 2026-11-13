"""주행 00000128 정체 구간: 앞차 추종 감속·재가속을 longitudinalPlan(20Hz) 시점마다 뽑는다.
기기에서 manager 환경으로 실행한다: python3 extract_long.py <출력.csv> <rlog 경로...> (읽기 전용)"""
import csv, sys, datetime
from opendbc.can.packer import CANPacker
from opendbc.can.parser import get_raw_value
from openpilot.tools.lib.logreader import LogReader

dbc = CANPacker("hyundai_canfd_generated").dbc
SCC = dbc.name_to_msg["SCC_CONTROL"].sigs
KST = datetime.timezone(datetime.timedelta(hours=9))
F = ["seg", "git", "wall", "mono", "vEgo", "aEgo", "gas", "brake", "standstill", "vCruise", "softHold",
     "enabled", "longActive", "accelCmd", "personality",
     "aTarget", "aTargetBase", "shouldStop", "allowThrottle", "source", "xState", "trafficState", "tFollow",
     "desiredDistance", "myDrivingMode", "hasLead", "fastLeadReason", "leadPreviewAccel", "aChangeCost", "vTargetNow", "jTargetNow",
     "l1Status", "l1dRel", "l1vRel", "l1vLead", "l1aLead", "l1Radar", "l1Prob", "l2Status", "l2dRel",
     "sccMode", "sccStop", "sccReq", "sccRaw", "sccJL", "sccJU"]

def main():
  out, paths = sys.argv[1], sys.argv[2:]
  with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=F); w.writeheader()
    for path in paths:
      seg = path.split("/")[-2].split("--")[-1]
      st = {k: "" for k in F}; base = None
      for m in LogReader(path):
        k = m.which()
        if k == "initData":
          base = (m.initData.wallTimeNanos, m.logMonoTime); st["git"] = m.initData.gitCommit[:9]
        elif k == "carState":
          c = m.carState
          st.update(vEgo=round(c.vEgo, 3), aEgo=round(c.aEgo, 3), gas=int(c.gasPressed), brake=int(c.brakePressed),
                    standstill=int(c.standstill), vCruise=round(c.vCruise, 1), softHold=getattr(c, "softHoldActive", ""))
        elif k == "carControl":
          c = m.carControl
          st.update(enabled=int(c.enabled), longActive=int(c.longActive), accelCmd=round(c.actuators.accel, 3))
        elif k == "selfdriveState":
          st["personality"] = str(m.selfdriveState.personality)
        elif k == "radarState":
          r = m.radarState
          for p, l in (("l1", r.leadOne),):
            st.update({p+"Status": int(l.status), p+"dRel": round(l.dRel, 2), p+"vRel": round(l.vRel, 2), p+"vLead": round(l.vLead, 2),
                       p+"aLead": round(l.aLeadK, 2), p+"Radar": int(l.radar), p+"Prob": round(l.modelProb, 2)})
          st.update(l2Status=int(r.leadTwo.status), l2dRel=round(r.leadTwo.dRel, 2))
        elif k == "sendcan":
          for x in m.sendcan:
            if x.address == 0x1A0 and x.src == 0:
              v = {n: get_raw_value(x.dat, s) * s.factor + s.offset for n, s in SCC.items() if n in ("ACCMode", "StopReq", "aReqValue", "aReqRaw", "JerkLowerLimit", "JerkUpperLimit")}
              st.update(sccMode=v["ACCMode"], sccStop=v["StopReq"], sccReq=round(v["aReqValue"], 3), sccRaw=round(v["aReqRaw"], 3),
                        sccJL=round(v["JerkLowerLimit"], 2), sccJU=round(v["JerkUpperLimit"], 2))
        elif k == "longitudinalPlan":
          p = m.longitudinalPlan
          row = dict(st)
          row.update(seg=seg, mono=m.logMonoTime, aTarget=round(p.aTarget, 3), aTargetBase=round(p.aTargetBase, 3), shouldStop=int(p.shouldStop),
                     allowThrottle=int(p.allowThrottle), source=str(p.longitudinalPlanSource), xState=p.xState, trafficState=p.trafficState,
                     tFollow=round(p.tFollow, 3), desiredDistance=round(p.desiredDistance, 2), myDrivingMode=p.myDrivingMode, hasLead=int(p.hasLead),
                     fastLeadReason=str(p.fastLeadReason), leadPreviewAccel=round(p.leadPreviewAccel, 3), aChangeCost=round(p.aChangeCost, 3),
                     vTargetNow=round(p.vTargetNow, 3), jTargetNow=round(p.jTargetNow, 3))
          if base:
            row["wall"] = datetime.datetime.fromtimestamp((base[0] + m.logMonoTime - base[1]) / 1e9, KST).strftime("%H:%M:%S.%f")[:11]
          w.writerow(row)

if __name__ == "__main__":
  main()

"""Generate deterministic timetable CSV demo data according to requirements:
- Mon-Fri: 13:00-14:00 Lunch (Break) for every room.
- Sat: 09:00-13:00 only, everything else Off.
- Sun: Off (hours 9-16 marked Free/Off, or 09-17 Off).
- B101 Seminar Hall exact schedule:
  Mon-Fri:
    09:00-11:00 Occupied: Guest lecture / workshop
    11:00-12:00 Free: Free period
    12:00-13:00 Occupied: Department seminar
    13:00-14:00 Break: Lunch
    14:00-16:00 Occupied: Placement talk / technical event
    16:00-17:00 Free: Free period
  Sat:
    09:00-10:00 Free: Free period
    10:00-12:00 Occupied: Placement training
    12:00-13:00 Free: Free period
- A204 (CSE Lab): Free 10:00-11:00 every weekday. Lab block e.g. 14:00-17:00.
- Labs/workshops: 3-hour practical block (09:00-12:00 or 14:00-17:00).
- Offices: Occupied 09:00-13:00 and 14:00-17:00 Mon-Fri, 09:00-13:00 Sat.
- Classrooms: 5-6 occupied periods, 1-2 free periods.
"""

import csv
import json

with open("d:/Projects/energy-system/energy-system/backend/app/demo_data/campus_demo.json", "r") as f:
    campus = json.load(f)

rooms = []
for blk in campus["blocks"]:
    for fl in blk["floors"]:
        for rm in fl["rooms"]:
            rooms.append(rm)

# Subjects by department
DEPT_SUBJECTS = {
    "Computer Science and Engineering (CSE)": ["Data Structures", "DBMS", "Operating Systems", "Computer Networks", "Algorithms"],
    "Computer Science and Design (CSD)": ["Data Science", "UI/UX Design", "Visualization", "Web Development", "AI Basics"],
    "Information Technology (IT)": ["Web Technology", "Cloud Computing", "Software Engineering", "Cyber Security", "Mobile App Dev"],
    "Biotechnology": ["Genetics", "Bioprocess", "Cell Biology", "Immunology", "Bioinformatics"],
    "Mechatronics Engineering (MCT)": ["Robotics", "PLC Programming", "Sensors and Actuators", "Hydraulics", "Microcontrollers"],
    "Electronics and Communication Engineering (ECE)": ["Digital Electronics", "VLSI", "Signals and Systems", "Communication Engineering", "Embedded Systems"],
    "Civil Engineering": ["Surveying", "Structural Analysis", "Concrete Technology", "Geotechnical Engineering", "Fluid Mechanics"],
    "Electrical and Electronics Engineering (EEE)": ["Circuit Theory", "Power Systems", "Control Systems", "Electrical Machines", "Power Electronics"],
    "Automobile Engineering": ["IC Engines", "Vehicle Dynamics", "Automotive Electricals", "Chassis Design", "Transmission Systems"],
    "General Science and Humanities": ["Engineering Physics", "Engineering Chemistry", "Calculus and Linear Algebra", "Technical English", "Environmental Studies"],
    "Administration": ["Administrative Work", "Executive Operations", "Finance & Accounts", "Faculty Meeting"]
}

timetable_rows = []

HOURS = list(range(9, 17)) # 9 to 16 (which represents 9:00-10:00 up to 16:00-17:00)

for rm in rooms:
    code = rm["code"]
    rtype = rm["type"]
    dept = rm["dept"]
    subjects = DEPT_SUBJECTS.get(dept, ["General Lecture", "Core Subject", "Elective", "Seminar", "Tutorial"])
    
    for day in range(7): # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
        for hour in HOURS:
            # Sunday
            if day == 6:
                status = "Free"
                activity = "Holiday / Campus Closed"
                timetable_rows.append((code, day, hour, activity, status))
                continue
                
            # Saturday afternoon
            if day == 5 and hour >= 13:
                status = "Free"
                activity = "Campus Closed (Weekend)"
                timetable_rows.append((code, day, hour, activity, status))
                continue
                
            # Weekday Lunch
            if day < 5 and hour == 13:
                status = "Break"
                activity = "Lunch"
                timetable_rows.append((code, day, hour, activity, status))
                continue
                
            # SPECIAL CASE: B101 Seminar Hall
            if code == "B101":
                if day < 5: # Mon-Fri
                    if hour in (9, 10):
                        status = "Occupied"
                        activity = "Guest lecture / workshop"
                    elif hour == 11:
                        status = "Free"
                        activity = "Free period"
                    elif hour == 12:
                        status = "Occupied"
                        activity = "Department seminar"
                    elif hour in (14, 15):
                        status = "Occupied"
                        activity = "Placement talk / technical event"
                    elif hour == 16:
                        status = "Free"
                        activity = "Free period"
                elif day == 5: # Sat
                    if hour in (10, 11):
                        status = "Occupied"
                        activity = "Placement training"
                    else:
                        status = "Free"
                        activity = "Free period"
                timetable_rows.append((code, day, hour, activity, status))
                continue

            # SPECIAL CASE: A204 (CSE Lab 2)
            if code == "A204":
                if day < 5:
                    if hour == 10:
                        status = "Free"
                        activity = "Lab Maintenance / Free Slot"
                    elif hour in (14, 15, 16):
                        status = "Occupied"
                        activity = "Operating Systems Practical Lab"
                    elif hour in (9, 11, 12):
                        status = "Free" if hour == 12 else "Occupied"
                        activity = "Open Lab / Self-study" if hour == 12 else "DBMS Practical Lab"
                elif day == 5:
                    status = "Occupied" if hour in (9, 10) else "Free"
                    activity = "Project Work Lab" if hour in (9, 10) else "Free Slot"
                timetable_rows.append((code, day, hour, activity, status))
                continue

            # OFFICES
            if rtype == "Office":
                if day < 5:
                    status = "Occupied"
                    activity = f"{rm['name']} Regular Hours"
                elif day == 5:
                    status = "Occupied" if hour < 13 else "Free"
                    activity = f"{rm['name']} Half-Day Hours" if hour < 13 else "Office Closed"
                timetable_rows.append((code, day, hour, activity, status))
                continue

            # LABS AND WORKSHOPS
            if rtype in ("Lab", "Workshop"):
                if day < 5:
                    # Alternating morning (9-12) or afternoon (14-17) practical blocks
                    is_morning = ((int(code[1:]) + day) % 2 == 0)
                    if is_morning and hour in (9, 10, 11):
                        status = "Occupied"
                        subj = subjects[(day) % len(subjects)]
                        activity = f"{subj} Practical"
                    elif not is_morning and hour in (14, 15, 16):
                        status = "Occupied"
                        subj = subjects[(day + 2) % len(subjects)]
                        activity = f"{subj} Practical"
                    else:
                        status = "Free"
                        activity = "Lab Free / Preparation"
                elif day == 5:
                    if hour in (9, 10, 11):
                        status = "Occupied"
                        activity = f"{subjects[0]} Project Session"
                    else:
                        status = "Free"
                        activity = "Lab Closed"
                timetable_rows.append((code, day, hour, activity, status))
                continue

            # CLASSROOMS
            if rtype == "Classroom":
                if day < 5:
                    # 5-6 occupied periods, 1-2 free periods
                    free_hour = 9 + ((int(code[1:]) * 2 + day) % 6)
                    if free_hour == 13:
                        free_hour = 11
                    
                    if hour == free_hour or (hour == 16 and (int(code[1:]) + day) % 3 == 0):
                        status = "Free"
                        activity = "Self-study / Library Hour"
                    else:
                        status = "Occupied"
                        subj = subjects[(hour + day) % len(subjects)]
                        activity = f"{subj} Lecture"
                elif day == 5:
                    if hour in (9, 10, 11):
                        status = "Occupied"
                        subj = subjects[(day) % len(subjects)]
                        activity = f"{subj} Tutorial"
                    else:
                        status = "Free"
                        activity = "Free / Mentoring Slot"
                timetable_rows.append((code, day, hour, activity, status))
                continue

# Write to CSV
out_path = "d:/Projects/energy-system/energy-system/backend/app/demo_data/timetable_demo.csv"
with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["room_code", "day", "hour", "activity", "status"])
    for row in timetable_rows:
        writer.writerow(row)

print(f"Generated {len(timetable_rows)} timetable slots in {out_path}")


from app import app, db, ParkingSlot
with app.app_context():
    db.drop_all()
    db.create_all()
    for slot in ["A1", "A2", "A3"]:
        db.session.add(ParkingSlot(slot_id=slot, status="Available"))
    db.session.commit()
    print("Database reset with A1, A2, A3")

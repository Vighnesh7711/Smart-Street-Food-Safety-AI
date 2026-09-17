from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class FoodItem(Base):
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, index=True)
    stall_id = Column(Integer, ForeignKey("stalls.id"), nullable=False)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)

    stall = relationship("Stall", backref="food_items")

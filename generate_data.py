import random
import pandas as pd
from datetime import datetime, timedelta

data = []
departments = [1, 2, 3, 4]
brands = ['Ford', 'Fiat', 'Mercedes', 'Renault', 'Volkswagen', 'Peugeot']
models = ['Transit', 'Doblo', 'Atego', 'Fluence', 'Caddy', 'Boxer']
standards = {1: 12, 2: 10, 3: 25, 4: 8}  

start_date = datetime(2024, 1, 1)

for vehicle_id in range(1, 101):
    plate = f"07 AAA {vehicle_id:03d}"
    dept = random.choice(departments)
    brand = random.choice(brands)
    model = random.choice(models)
    std = standards[dept] + random.uniform(-1, 1)
    for day in range(120):  
        date = start_date + timedelta(days=day)
        km = random.randint(40, 300)
        fuel = (km / 100) * std * random.uniform(0.8, 1.5)  
        data.append([plate, brand, model, dept, round(std, 2), date.strftime('%Y-%m-%d'), km, round(fuel, 2)])

df = pd.DataFrame(data, columns=['plate_number', 'brand', 'model', 'department_id', 'standard_fuel_per_100km', 'usage_date', 'daily_km', 'fuel_liters'])
df.to_csv('data/sample_data.csv', index=False)
print("Yeni veri seti oluşturuldu.")
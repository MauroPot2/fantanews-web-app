# utils/fantacalcio_utils.py
def points_to_goals(points):
    """
    Converte punteggio fantacalcio in gol
    66+ punti = 1 gol, poi +1 gol ogni 6 punti
    """
    if points < 66:
        return 0
    
    # Formula: gol = 1 + ((punti - 66) // 6)
    goals = 1 + int((points - 66) // 6)
    return goals

def goals_to_points_range(goals):
    """
    Converte gol in range di punti
    Utile per capire il range di punteggio
    """
    if goals == 0:
        return (0, 65.99)
    
    min_points = 66 + (goals - 1) * 6
    max_points = min_points + 5.99
    
    return (min_points, max_points)

def get_goal_description(points):
    """
    Ritorna descrizione del risultato
    """
    goals = points_to_goals(points)
    
    if goals == 0:
        return "Sconfitta"
    elif goals == 1:
        return "Vittoria di misura"
    elif goals == 2:
        return "Vittoria convincente" 
    elif goals == 3:
        return "Vittoria netta"
    elif goals >= 4:
        return "Vittoria schiacciante"

# Test della funzione
if __name__ == "__main__":
    test_points = [60, 66, 67, 72, 78, 84, 90, 96]
    
    for points in test_points:
        goals = points_to_goals(points)
        desc = get_goal_description(points)
        print(f"{points:.1f} punti = {goals} gol ({desc})")

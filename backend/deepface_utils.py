from deepface import DeepFace

def reconhecer_usuario(img_path, db_paths):
    # db_paths: lista de caminhos das imagens dos usuários cadastrados
    results = []
    for db_img in db_paths:
        try:
            result = DeepFace.verify(img_path, db_img)
            # Se similaridade for alta (distance baixa)
            if result['verified']:
                results.append({"db_img": db_img, "distance": result["distance"]})
        except Exception:
            continue
    # Retorna a menor distância (melhor match) se encontrado
    if results:
        return min(results, key=lambda x: x["distance"])
    return None

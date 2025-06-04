import cv2
import numpy as np

def align_using_features(copy_img, template_img):
    img1 = cv2.cvtColor(template_img, cv2.COLOR_BGR2GRAY)
    img2 = cv2.cvtColor(copy_img, cv2.COLOR_BGR2GRAY)

    sift = cv2.SIFT_create()

    kp1, des1 = sift.detectAndCompute(img1, None)
    kp2, des2 = sift.detectAndCompute(img2, None)

    index_params = dict(algorithm=1, trees=5)
    search_params = dict(checks=50)
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    matches = flann.knnMatch(des1, des2, k=2)

    good = []
    for m, n in matches:
        if m.distance < 0.7 * n.distance:
            good.append(m)

    if len(good) < 10:
        print(" Pas assez de bons points pour estimer l'homographie")
        return copy_img, False

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    M, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)

    if M is None:
        print(" Homographie échouée")
        return copy_img, False

    h, w = template_img.shape[:2]
    aligned = cv2.warpPerspective(copy_img, M, (w, h))

    return aligned, True



def extract_blocks(aligned_img):
    block_name = aligned_img[140:1357, 240:1550]  #  SURNAME + FIRST NAME
    block_questions = aligned_img[1357:2280, 190:1590]  # Q1 à Q200
    return block_name, block_questions


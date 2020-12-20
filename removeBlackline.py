import cv2
import utilities as util
import numpy as np

baseImg = cv2.imread("results/warpedResImg.png")
originImg = cv2.imread("results/intermediateResult1.png")
# util.display("Origin img", originImg)

originImgGray = cv2.cvtColor(originImg, cv2.COLOR_BGR2GRAY)
baseImgGray = cv2.cvtColor(baseImg, cv2.COLOR_BGR2GRAY)
# util.display("Origin img gray", originImgGray)
ret, mask1 = cv2.threshold(originImgGray, 18, 255, cv2.THRESH_BINARY_INV)
util.display("mask1", mask1)
mask2 = np.float32(mask1)/255

for row in range(mask2.shape[0]):
	for col in range(mask2.shape[1]):
		if mask2[row, col] == 1.0 and baseImgGray[row, col] != 0.0:
			# print("lal")
			#blue
			tmpBlue = (baseImg[row, col-1][0] + baseImg[row, col+1][0] + baseImg[row-1, col][0] + baseImg[row+1, col][0])/4.0
			#green
			tmpGreen = (baseImg[row, col-1][1] + baseImg[row, col+1][1] + baseImg[row-1, col][1] + baseImg[row+1, col][1])/4.0
			#red
			tmpRed = (baseImg[row, col-1][2] + baseImg[row, col+1][2] + baseImg[row-1, col][2] + baseImg[row+1, col][2])/4.0
			originImg[row,col][0]=255
			originImg[row,col][1]=255
			originImg[row,col][2]=255

util.display("After fix", originImg)




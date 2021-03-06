import cv2
import numpy as np
import utilities as util
import geometry as gm
import copy

class Combiner:
	def __init__(self,imageList_,dataMatrix_):
		'''
		:param imageList_: List of all images in dataset.
		:param dataMatrix_: Matrix with all pose data in dataset.
		:return:
		'''
		self.imageList = []
		self.dataMatrix = dataMatrix_
		detector = cv2.ORB()
		for i in range(0,len(imageList_)):
			image = imageList_[i][::2,::2,:] #downsample the image to speed things up. 4000x3000 is huge!
			# image = imageList_[i] #downsample the image to speed things up. 4000x3000 is huge!
			M = gm.computeUnRotMatrix(self.dataMatrix[i,:])
			#Perform a perspective transformation based on pose information.
			#Ideally, this will mnake each image look as if it's viewed from the top.
			#We assume the ground plane is perfectly flat.
			correctedImage = gm.warpPerspectiveWithPadding(image,M)
			self.imageList.append(correctedImage) #store only corrected images to use in combination
		# self.resultImage = self.imageList[0]
		cv2.imwrite("results/intermediateResult.png",self.imageList[0])
	def createMosaic(self):
		for i in range(1,len(self.imageList)):
			self.combine(i)
			print("Processing photo "+str(i))
		return self.resultImage

	def combine(self, index2):
		self.resultImage = cv2.imread("results/intermediateResult.png")
		'''
		:param index2: index of self.imageList and self.kpList to combine with self.referenceImage and self.referenceKeypoints
		:return: combination of reference image and image at index 2
		'''

		#Attempt to combine one pair of images at each step. Assume the order in which the images are given is the best order.
		#This intorduces drift!
		image1 = copy.copy(self.imageList[index2 - 1])
		image2 = copy.copy(self.imageList[index2])

		'''
		Descriptor computation and matching.
		Idea: Align the images by aligning features.
		'''
		# detector = cv2.SURF(500) #SURF showed best results
		detector = cv2.ORB_create() #SURF showed best results

		# detector.extended = True
		gray1 = cv2.cvtColor(image1,cv2.COLOR_BGR2GRAY)
		# gray1 = cv2.cvtColor(self.resultImage,cv2.COLOR_BGR2GRAY)
		ret1, mask1 = cv2.threshold(gray1,1,255,cv2.THRESH_BINARY)
		kp1, descriptors1 = detector.detectAndCompute(gray1,mask1) #kp = keypoints

		gray2 = cv2.cvtColor(image2,cv2.COLOR_BGR2GRAY)
		ret2, mask2 = cv2.threshold(gray2,1,255,cv2.THRESH_BINARY)
		kp2, descriptors2 = detector.detectAndCompute(gray2,mask2)

		#Visualize matching procedure.
		# keypoints1Im = self.resultImage.copy()
		# keypoints2Im = image2.copy()
		# cv2.drawKeypoints(self.resultImage, kp1, keypoints1Im,color=(0,0,255))
		# util.display("KEYPOINTS1",keypoints1Im)
		# cv2.drawKeypoints(image2,kp2,keypoints2Im,color=(0,0,255))
		# util.display("KEYPOINTS2",keypoints2Im)

		matcher = cv2.BFMatcher() #use brute force matching
		matches = matcher.knnMatch(descriptors2,descriptors1, k=2) #find pairs of nearest matches
		#prune bad matches
		good = []
		for m,n in matches:
			if m.distance < 0.55*n.distance:
				good.append(m)
		matches = copy.copy(good)

		#Visualize matches
		matchDrawing = util.drawMatches(gray2,kp2,gray1,kp1,matches)
		util.display("matches",matchDrawing)

		#NumPy syntax for extracting location data from match data structure in matrix form
		src_pts = np.float32([ kp2[m.queryIdx].pt for m in matches ]).reshape(-1,1,2)
		dst_pts = np.float32([ kp1[m.trainIdx].pt for m in matches ]).reshape(-1,1,2)

		'''
		Compute Affine Transform
		Idea: Because we corrected for camera orientation, an affine transformation *should* be enough to align the images
		'''
		#Deprecated --stephen
		# A = cv2.estimateRigidTransform(src_pts,dst_pts,fullAffine=False) #false because we only want 5 DOF. we removed 3 DOF when we unrotated
		A, inliers = cv2.estimateAffinePartial2D(src_pts,dst_pts) #false because we only want 5 DOF. we removed 3 DOF when we unrotated
		if type(A) == type(None) : #RANSAC sometimes fails in estimateRigidTransform(). If so, try full homography. OpenCV RANSAC implementation for homography is more robust.
		# if A.size == 0: #RANSAC sometimes fails in estimateRigidTransform(). If so, try full homography. OpenCV RANSAC implementation for homography is more robust.
			HomogResult = cv2.findHomography(src_pts,dst_pts,method=cv2.RANSAC)
			H = HomogResult[0]

		'''
		Compute 4 Image Corners Locations
		Idea: Same process as warpPerspectiveWithPadding() excewpt we have to consider the sizes of two images. Might be cleaner as a function.
		'''
		height1,width1 = image1.shape[:2]
		height2,width2 = image2.shape[:2]
		corners1 = np.float32(([0,0],[0,height1],[width1,height1],[width1,0]))
		corners2 = np.float32(([0,0],[0,height2],[width2,height2],[width2,0]))
		warpedCorners2 = np.zeros((4,2))
		for i in range(0,4):
			cornerX = corners2[i,0]
			cornerY = corners2[i,1]
			# if A != None: #check if we're working with affine transform or perspective transform
			if type(A) == type(None) : #RANSAC sometimes fails in estimateRigidTransform(). If so, try full homography. OpenCV RANSAC implementation for homography is more robust.
				warpedCorners2[i,0] = (H[0,0]*cornerX + H[0,1]*cornerY + H[0,2])/(H[2,0]*cornerX + H[2,1]*cornerY + H[2,2])
				warpedCorners2[i,1] = (H[1,0]*cornerX + H[1,1]*cornerY + H[1,2])/(H[2,0]*cornerX + H[2,1]*cornerY + H[2,2])
			else:
				warpedCorners2[i][0] = A[0][0]*cornerX + A[0][1]*cornerY + A[0][2]
				warpedCorners2[i][1] = A[1][0]*cornerX + A[1][1]*cornerY + A[1][2]
		allCorners = np.concatenate((corners1, warpedCorners2), axis=0)
		[xMin, yMin] = np.int32(allCorners.min(axis=0).ravel() - 0.5)
		[xMax, yMax] = np.int32(allCorners.max(axis=0).ravel() + 0.5)

		'''Compute Image Alignment and Keypoint Alignment'''
		translation = np.float32(([1,0,-1*xMin],[0,1,-1*yMin],[0,0,1]))
		warpedResImg = cv2.warpPerspective(self.resultImage, translation, (xMax-xMin, yMax-yMin))
		# cv2.imwrite("results/warpedResImg.png",warpedResImg)
		if type(A) == type(None) : #RANSAC sometimes fails in estimateRigidTransform(). If so, try full homography. OpenCV RANSAC implementation for homography is more robust.
		# if A.size == 0:
			fullTransformation = np.dot(translation,H) #again, images must be translated to be 100% visible in new canvas
			warpedImage2 = cv2.warpPerspective(image2, fullTransformation, (xMax-xMin, yMax-yMin))
		else:
			warpedImageTemp = cv2.warpPerspective(image2, translation, (xMax-xMin, yMax-yMin))
			warpedImage2 = cv2.warpAffine(warpedImageTemp, A, (xMax-xMin, yMax-yMin))
		self.imageList[index2] = copy.copy(warpedImage2) #crucial: update old images for future feature extractions

		# result = cv2.addWeighted(warpedResImg, 0, warpedImage2, 1, 0.0)
		# util.display("tempResult", result)

		# resGray = cv2.cvtColor(self.resultImage,cv2.COLOR_BGR2GRAY)
		# warpedResGray = cv2.warpPerspective(resGray, translation, (xMax-xMin, yMax-yMin))

		# warpedImage2Resize = cv2.resize(warpedImage2, (warpedImage2.shape[1]+1, warpedImage2.shape[0]+1), 0, 0, cv2.INTER_AREA)
		warpedImg2Gray = cv2.cvtColor(warpedImage2, cv2.COLOR_BGR2GRAY)
		# warpedImg2Gray = cv2.blur(warpedImg2Gray, (8,8))
		# util.display("blur", warpedImg2Gray)

		'''Compute Mask for Image Combination'''
		# ret, mask1 = cv2.threshold(warpedResGray,1,255,cv2.THRESH_BINARY_INV)
		ret, mask1 = cv2.threshold(warpedImg2Gray, 1, 255, cv2.THRESH_BINARY_INV)
		mask3 = np.float32(mask1)/255

		#apply mask
		# tmpRow = warpedImage2Resize.shape[0]
		# tmpCol = warpedImage2Resize.shape[1]
		# warpedResImgcp = copy.copy(warpedResImg)
		warpedResImg[:,:,0] = warpedResImg[:,:,0] * mask3
		warpedResImg[:,:,1] = warpedResImg[:,:,1] * mask3
		warpedResImg[:,:,2] = warpedResImg[:,:,2] * mask3
		# warpedResImg[:tmpRow,:tmpCol,0] = warpedResImg[:tmpRow,:tmpCol,0] * mask3
		# warpedResImg[:tmpRow,:tmpCol,1] = warpedResImg[:tmpRow,:tmpCol,1] * mask3
		# warpedResImg[:tmpRow,:tmpCol,2] = warpedResImg[:tmpRow,:tmpCol,2] * mask3
		# util.display("after mask", warpedResImg)

		result = warpedResImg + warpedImage2

		#Remove black line
		# resultGray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
		# ret, mask4 = cv2.threshold(resultGray, 25, 255, cv2.THRESH_BINARY_INV)
		# util.display("resultGray", mask4)

		# mask5 = np.float32(mask4)/255

		# util.display("warpedResImgcp origin", warpedResImgcp)
		# warpedResImgcp[:,:,0] = warpedResImgcp[:,:,0] * mask5
		# warpedResImgcp[:,:,1] = warpedResImgcp[:,:,1] * mask5
		# warpedResImgcp[:,:,2] = warpedResImgcp[:,:,2] * mask5
		# util.display("warpedResImgcp", warpedResImgcp)

		# util.display("result1",result)
		# result = result + warpedResImgcp

		#visualize and save result
		self.resultImage = result
		# util.display("result2",result)

		cv2.imwrite("results/intermediateResult.png",result)
		return result


import numpy as np
import cv2
import math as m
import copy
import utilities as util

def computeUnRotMatrix(pose):
    '''
    See http://planning.cs.uiuc.edu/node102.html. Undoes the rotation of the craft relative to the world frame.
    :param pose: A 1x6 NumPy ndArray containing pose information in [X,Y,Z,Y,P,R] format
    :return: A 3x3 rotation matrix that removes perspective distortion from the image to which it is applied.
    '''
    a = pose[3]*np.pi/180 #alpha
    b = pose[4]*np.pi/180 #beta
    g = pose[5]*np.pi/180 #gamma
    Rz = np.array(([m.cos(a), -1*m.sin(a),    0],
                   [m.sin(a),    m.cos(a),    0],
                   [       0,           0,     1]))

    Ry = np.array(([ m.cos(b),           0,     m.sin(b)],
                   [        0,           1,            0],
                   [-1*m.sin(b),           0,     m.cos(b)]))

    Rx = np.array(([        1,           0,            0],
                   [        0,    m.cos(g),  -1*m.sin(g)],
                   [        0,    m.sin(g),     m.cos(g)]))
    Ryx = np.dot(Rx,Ry)
    R = np.dot(Rz,Ryx)
    R[0,2] = 0
    R[1,2] = 0
    R[2,2] = 1
    Rtrans = R.transpose()
    InvR = np.linalg.inv(Rtrans)
    return InvR

def warpPerspectiveWithPadding(image,transformation,kp):
    '''
    :param image: ndArray image
    :param transformation: 3x3 ndArray representing perspective trransformation
    :param kp: keypoints associated with image
    :return: transformed image and transformed keypoints
    '''

    height = image.shape[0]
    width = image.shape[1]
    corners = np.float32([[0,0],[0,height],[width,height],[width,0]]).reshape(-1,1,2)

    warpedCorners = cv2.perspectiveTransform(corners, transformation)
    [xMin, yMin] = np.int32(warpedCorners.min(axis=0).ravel() - 0.5)
    [xMax, yMax] = np.int32(warpedCorners.max(axis=0).ravel() + 0.5)
    translation = np.array(([1,0,-1*xMin],[0,1,-1*yMin],[0,0,1]))
    fullTransformation = np.dot(translation,transformation)
    result = cv2.warpPerspective(image, fullTransformation, (xMax-xMin, yMax-yMin))
    newKP = perspectiveTransformKeypoints(kp,fullTransformation)
    return result, newKP

def affineTransformKeypoints(kp,A):
    '''
    :param kp: keypoints as returned by funcitons like
    :param A: 2x3 affine transformation matrix
    :return: new set of transformed keypoints
    '''
    newKP = copy.copy(kp)
    for i in range(0,len(kp)):
        oldX = kp[i].pt[0]
        oldY = kp[i].pt[1]
        newX = A[0,0]*oldX + A[0,1]*oldY + A[0,2]
        newY = A[1,0]*oldX + A[1,1]*oldY + A[1,2]
        newKP[i].pt = (newX,newY)
    return newKP

def perspectiveTransformKeypoints(kp, M):
    '''
    :param kp: keypoints as returned by funcitons like
    :param M: 3x3 transformation matrix
    :return: new set of transformed keypoints
    '''
    newKP = copy.copy(kp)
    for i in range(0,len(kp)):
        oldX = kp[i].pt[0]
        oldY = kp[i].pt[1]
        newX = (M[0,0]*oldX + M[0,1]*oldY + M[0,2])/(M[2,0]*oldX + M[2,1]*oldY + M[2,2])
        newY = (M[1,0]*oldX + M[1,1]*oldY + M[1,2])/(M[2,0]*oldX + M[2,1]*oldY + M[2,2])
        newKP[i].pt = (newX,newY)
    return newKP
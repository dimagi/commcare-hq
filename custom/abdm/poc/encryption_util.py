import os
import uuid
import json
import subprocess

from custom.abdm.poc.const import FIDELIUS_CLI_PATH

dirname = os.path.dirname(os.path.abspath(__file__))
binPath = FIDELIUS_CLI_PATH


def execFideliusCli(args):
    fideliusCommand = [binPath] + args
    result = subprocess.run(
        fideliusCommand, stdout=subprocess.PIPE, encoding='UTF-8'
    )
    try:
        return json.loads(result.stdout)
    except Exception:
        print(
            f'ERROR · execFideliusCli · Command: {" ".join(args)}\n{result.stdout}'
        )


def getEcdhKeyMaterial():
    result = execFideliusCli(['gkm'])
    return result


def writeParamsToFile(*params):
    fileContents = '\n'.join(params)
    filePath = os.path.join(dirname, 'temp', f'{str(uuid.uuid4())}.txt')
    os.makedirs(os.path.dirname(filePath), exist_ok=True)
    f = open(filePath, 'a')
    f.write(fileContents)
    f.close()
    return filePath


def removeFileAtPath(filePath):
    os.remove(filePath)


def encryptData(encryptParams):
    paramsFilePath = writeParamsToFile(
        'e',
        encryptParams['stringToEncrypt'],
        encryptParams['senderNonce'],
        encryptParams['requesterNonce'],
        encryptParams['senderPrivateKey'],
        encryptParams['requesterPublicKey']
    )
    result = execFideliusCli(['-f', paramsFilePath])
    removeFileAtPath(paramsFilePath)
    return result


def decryptData(decryptParams):
    paramsFilePath = writeParamsToFile(
        'd',
        decryptParams['encryptedData'],
        decryptParams['requesterNonce'],
        decryptParams['senderNonce'],
        decryptParams['requesterPrivateKey'],
        decryptParams['senderPublicKey']
    )
    result = execFideliusCli(['-f', paramsFilePath])
    removeFileAtPath(paramsFilePath)
    return result


def runExample(stringToEncrypt):
    requesterKeyMaterial = getEcdhKeyMaterial()
    senderKeyMaterial = getEcdhKeyMaterial()

    print(json.dumps({
        'requesterKeyMaterial': requesterKeyMaterial,
        'senderKeyMaterial': senderKeyMaterial
    }, indent=4))

    encryptionResult = encryptData({
        'stringToEncrypt': stringToEncrypt,
        'senderNonce': senderKeyMaterial['nonce'],
        'requesterNonce': requesterKeyMaterial['nonce'],
        'senderPrivateKey': senderKeyMaterial['privateKey'],
        'requesterPublicKey': requesterKeyMaterial['publicKey']
    })

    encryptionWithX509PublicKeyResult = encryptData({
        'stringToEncrypt': stringToEncrypt,
        'senderNonce': senderKeyMaterial['nonce'],
        'requesterNonce': requesterKeyMaterial['nonce'],
        'senderPrivateKey': senderKeyMaterial['privateKey'],
        'requesterPublicKey': requesterKeyMaterial['x509PublicKey']
    })

    print(json.dumps({
        'encryptedData': encryptionResult['encryptedData'],
        'encryptedDataWithX509PublicKey': encryptionWithX509PublicKeyResult['encryptedData']
    }, indent=4))

    decryptionResult = decryptData({
        'encryptedData': encryptionResult['encryptedData'],
        'requesterNonce': requesterKeyMaterial['nonce'],
        'senderNonce': senderKeyMaterial['nonce'],
        'requesterPrivateKey': requesterKeyMaterial['privateKey'],
        'senderPublicKey': senderKeyMaterial['publicKey']
    })

    decryptionResultWithX509PublicKey = decryptData({
        'encryptedData': encryptionResult['encryptedData'],
        'requesterNonce': requesterKeyMaterial['nonce'],
        'senderNonce': senderKeyMaterial['nonce'],
        'requesterPrivateKey': requesterKeyMaterial['privateKey'],
        'senderPublicKey': senderKeyMaterial['x509PublicKey']
    })

    print(json.dumps({
        'decryptedData': decryptionResult['decryptedData'],
        'decryptedDataWithX509PublicKey': decryptionResultWithX509PublicKey['decryptedData']
    }, indent=4))


def main(stringToEncrypt='{"data": "There is no war in Ba Sing Se!"}'):
    runExample(stringToEncrypt)


if __name__ == '__main__':
    main()
